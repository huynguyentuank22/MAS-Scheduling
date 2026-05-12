"""External benchmark runner using adapter interfaces."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from .agent_registry import AgentRegistry
from .agent_runtime import AgentRuntime
from .benchmarks.gaia_lite import GAIALiteAdapter, get_gaia_lite_seed_memories
from .blackboard import Blackboard
from .evaluator import SchedulingEvaluator
from .memory_curator import MemoryCurator
from .memory_store import MemoryStore
from .orchestrator import Orchestrator
from .policy_engine import PolicyEngine
from .schemas import MemoryStatus, ProceduralControlMemory
from .trace_logger import TraceLogger


_VALIDATION_FIELDS = [
    "success_rate",
    "mean_score",
    "agent_output_schema_valid_rate",
    "parse_failure_rate",
    "repair_success_rate",
    "invalid_artifact_ref_rate",
    "memory_validation_failure_rate",
    "unsupported_lesson_rate",
    "overgeneralized_memory_rate",
    "curator_accept_rate",
    "curator_reject_rate",
]


class ExternalBenchmarkRunner:
    """Run one external benchmark variant through the orchestrator stack."""

    def __init__(
        self,
        benchmark_name: str,
        split: str,
        variant: str,
        output_dir: str = "experiments/gaia_lite_smoke",
        limit: int | None = None,
        seed: int = 42,
    ) -> None:
        self._benchmark_name = benchmark_name
        self._split = split
        self._variant = variant
        self._output_dir = Path(output_dir)
        self._limit = limit
        self._seed = seed

    def run(self) -> dict[str, Any]:
        adapter = self._build_adapter()
        tasks = adapter.load_tasks(split=self._split, limit=self._limit)
        variant_cfg = self._variant_config(self._variant)

        trace_dir = self._output_dir / "traces" / self._variant
        memory_dir = self._output_dir / "memories" / self._variant
        trace_dir.mkdir(parents=True, exist_ok=True)
        memory_dir.mkdir(parents=True, exist_ok=True)

        registry = AgentRegistry()
        runtime = AgentRuntime(seed=self._seed, failure_rate=0.25)
        memory_store = MemoryStore(memory_dir=str(memory_dir) if variant_cfg["use_memory"] else None)
        blackboard = Blackboard()
        policy_engine = PolicyEngine()
        trace_logger = TraceLogger(trace_dir=str(trace_dir))
        evaluator = SchedulingEvaluator()
        curator = MemoryCurator(memory_store, agent_registry=registry) if variant_cfg["use_curation"] else None

        if variant_cfg["use_memory"]:
            for mem in self._build_seed_memories(
                benchmark=self._benchmark_name,
                memory_source=variant_cfg["memory_source"],
                seed=self._seed,
            ):
                memory_store.put_procedural(mem)

        orchestrator = Orchestrator(
            registry=registry,
            runtime=runtime,
            memory_store=memory_store,
            blackboard=blackboard,
            policy_engine=policy_engine,
            trace_logger=trace_logger,
            evaluator=evaluator,
            curator=curator,
            use_memory=variant_cfg["use_memory"],
        )

        episode_results: list[dict[str, Any]] = []
        for idx, task in enumerate(tasks):
            metadata = adapter.get_task_metadata(task)
            prompt = adapter.get_task_prompt(task)
            task_descriptions = self._task_descriptions(prompt=prompt, metadata=metadata)

            result = orchestrator.run_episode(
                objective=prompt,
                task_descriptions=task_descriptions,
                benchmark_name=self._benchmark_name,
                task_family=str(metadata.get("task_family") or "unknown"),
            )

            workflow_id = result["workflow"].workflow_id
            artifacts = blackboard.list_artifacts(workflow_id=workflow_id)
            final_output = artifacts[-1].content if artifacts else ""
            external_eval = adapter.evaluate(task=task, final_output=final_output, artifacts=artifacts)
            internal_eval = result["evaluation"]

            retrieve_events = [d for d in result["decisions"] if d.chosen_action == "retrieve_memory"]
            retrieved_count = len(retrieve_events)
            eligible_count = sum(
                1
                for d in retrieve_events
                if bool((d.memory_influence or {}).get("eligible_to_influence", False))
            )
            blocked_count = sum(
                1
                for d in retrieve_events
                if (d.memory_influence or {}).get("blocked_reason")
            )

            ep_summary = {
                "episode_idx": idx,
                "task_id": str(task.get("task_id") or f"task-{idx + 1}"),
                "workflow_id": workflow_id,
                "task_family": str(metadata.get("task_family") or "unknown"),
                "task_pattern": str(metadata.get("task_pattern") or ""),
                "external_success": bool(external_eval.get("success", False)),
                "external_score": float(external_eval.get("score", 0.0)),
                "external_reason": str(external_eval.get("reason") or ""),
                "benchmark_success": internal_eval.benchmark_success,
                "benchmark_score": internal_eval.benchmark_score,
                "scheduling_scores": internal_eval.scheduling_scores,
                "memory_used": len(internal_eval.memory_used),
                "retrieved_count": retrieved_count,
                "eligible_count": eligible_count,
                "blocked_count": blocked_count,
                "curation_actions": self._serialize_curation_actions(result["curation_actions"]),
            }
            episode_results.append(ep_summary)

            status = "OK" if ep_summary["external_success"] else "FAIL"
            print(
                f"  Task {idx + 1:3d} | "
                f"{ep_summary['task_family']:20s} | "
                f"{status:4s} | "
                f"ext_score={ep_summary['external_score']:.2f} | "
                f"mem_used={ep_summary['memory_used']}"
            )

        summary = self._summarize(
            variant=self._variant,
            benchmark=self._benchmark_name,
            split=self._split,
            tasks=tasks,
            episode_results=episode_results,
            tools=adapter.provide_tools(),
            total_memories=len(memory_store.list_procedural()),
        )

        self._output_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = self._output_dir / "metrics.json"
        metrics_path.write_text(
            json.dumps({self._variant: summary}, indent=2, default=str),
            encoding="utf-8",
        )
        self._write_validation_report({self._variant: summary}, self._output_dir)

        print(f"Metrics saved to {metrics_path}")
        print(f"Validation report saved to {self._output_dir / 'validation_metrics_report.md'}")

        return {"results": {self._variant: summary}}

    def _build_adapter(self) -> GAIALiteAdapter:
        if self._benchmark_name == "gaia_lite":
            return GAIALiteAdapter()
        raise ValueError(f"Unsupported benchmark: {self._benchmark_name}")

    @staticmethod
    def _variant_config(variant: str) -> dict[str, Any]:
        variants = {
            "mas_no_memory": {
                "use_memory": False,
                "use_curation": False,
                "memory_source": "curated",
            },
            "mas_orchestrator_memory": {
                "use_memory": True,
                "use_curation": True,
                "memory_source": "curated",
            },
            "mas_shuffled_memory": {
                "use_memory": True,
                "use_curation": False,
                "memory_source": "shuffled",
            },
            "mas_random_memory": {
                "use_memory": True,
                "use_curation": False,
                "memory_source": "random",
            },
        }
        if variant not in variants:
            raise ValueError(f"Unsupported variant: {variant}")
        return variants[variant]

    @staticmethod
    def _build_seed_memories(
        benchmark: str,
        memory_source: str,
        seed: int,
    ) -> list[ProceduralControlMemory]:
        if benchmark != "gaia_lite":
            return []

        seed_defs = get_gaia_lite_seed_memories()
        families = list(seed_defs.keys())

        if memory_source in {"shuffled", "random", "shuffled_or_random"}:
            rng = random.Random(seed)
            targets = families[:]
            rng.shuffle(targets)
            if targets == families:
                targets = targets[1:] + targets[:1]
            mapping = dict(zip(families, targets))
        else:
            mapping = {family: family for family in families}

        out: list[ProceduralControlMemory] = []
        for source_family in families:
            payload = dict(seed_defs[source_family])
            trigger = dict(payload.get("trigger", {}))
            trigger["task_family"] = mapping[source_family]
            trigger["source_family"] = source_family
            payload["trigger"] = trigger

            out.append(
                ProceduralControlMemory(
                    trigger=payload.get("trigger", {}),
                    recommended_schedule=list(payload.get("recommended_schedule", [])),
                    avoid=list(payload.get("avoid", [])),
                    recommended_recovery=list(payload.get("recommended_recovery", [])),
                    confidence=float(payload.get("confidence", 0.75)),
                    status=MemoryStatus.ACTIVE,
                    supporting_episodes=["seeded"],
                )
            )
        return out

    @staticmethod
    def _task_descriptions(prompt: str, metadata: dict[str, Any]) -> list[str]:
        family = str(metadata.get("task_family") or "").strip().lower()
        prompt_line = f"Task prompt: {prompt}"
        templates = {
            "numeric_reasoning": [
                "Plan the numeric reasoning approach",
                "Use tools to gather relevant numeric facts",
                "Calculate the answer precisely",
                "Verify the numeric answer and write final response",
                prompt_line,
            ],
            "web_research": [
                "Plan the web research strategy",
                "Research sources and gather evidence",
                "Write the answer from evidence",
                "Verify claims and constraints before finalize",
                prompt_line,
            ],
            "multi_hop": [
                "Plan multi-hop reasoning steps",
                "Research first-hop and second-hop facts",
                "Critique reasoning consistency across hops",
                "Write a synthesized answer",
                "Verify final answer",
                prompt_line,
            ],
            "file_question": [
                "Plan file-reading and extraction approach",
                "Read relevant file content and extract evidence",
                "Write answer from extracted evidence",
                "Verify answer against file constraints",
                prompt_line,
            ],
            "verification_heavy": [
                "Plan verification-heavy workflow",
                "Research or gather conflicting evidence",
                "Critique source consistency",
                "Verify the final choice against constraints",
                "Write final answer",
                prompt_line,
            ],
        }
        return templates.get(family, [prompt_line])

    @staticmethod
    def _summarize(
        variant: str,
        benchmark: str,
        split: str,
        tasks: list[dict[str, Any]],
        episode_results: list[dict[str, Any]],
        tools: list[str],
        total_memories: int,
    ) -> dict[str, Any]:
        if not episode_results:
            return {
                "variant": variant,
                "benchmark": benchmark,
                "split": split,
                "total_tasks": 0,
                "success_rate": 0.0,
                "mean_score": 0.0,
                "episodes": [],
            }

        success_count = sum(1 for ep in episode_results if ep["external_success"])
        ext_scores = [float(ep["external_score"]) for ep in episode_results]

        def _mean_sched(name: str) -> float:
            vals = [float(ep["scheduling_scores"].get(name, 0.0)) for ep in episode_results]
            return round(sum(vals) / max(len(vals), 1), 3)

        def _sum_sched(name: str) -> int:
            return int(sum(int(ep["scheduling_scores"].get(name, 0)) for ep in episode_results))

        summary = {
            "variant": variant,
            "benchmark": benchmark,
            "split": split,
            "total_tasks": len(tasks),
            "success_count": success_count,
            "success_rate": round(success_count / max(len(episode_results), 1), 3),
            "mean_score": round(sum(ext_scores) / max(len(ext_scores), 1), 3),
            "dependency_violation_rate": _mean_sched("dependency_violation_rate"),
            "order_violation_rate": _mean_sched("order_violation_rate"),
            "missing_required_agent_rate": _mean_sched("missing_required_agent_rate"),
            "recovery_success_rate": _mean_sched("recovery_success_rate"),
            "memory_changed_scheduling_decisions": _sum_sched("memory_changed_scheduling_decisions"),
            "support_only_count": _sum_sched("support_only_count"),
            "changed_agent_selection_count": _sum_sched("changed_agent_selection_count"),
            "changed_ordering_count": _sum_sched("changed_ordering_count"),
            "changed_recovery_count": _sum_sched("changed_recovery_count"),
            "retrieved_count": int(sum(int(ep["retrieved_count"]) for ep in episode_results)),
            "eligible_count": int(sum(int(ep["eligible_count"]) for ep in episode_results)),
            "blocked_count": int(sum(int(ep["blocked_count"]) for ep in episode_results)),
            "agent_output_schema_valid_rate": _mean_sched("agent_output_schema_valid_rate"),
            "parse_failure_rate": _mean_sched("parse_failure_rate"),
            "repair_success_rate": _mean_sched("repair_success_rate"),
            "invalid_artifact_ref_rate": _mean_sched("invalid_artifact_ref_rate"),
            "memory_validation_failure_rate": _mean_sched("memory_validation_failure_rate"),
            "unsupported_lesson_rate": _mean_sched("unsupported_lesson_rate"),
            "overgeneralized_memory_rate": _mean_sched("overgeneralized_memory_rate"),
            "curator_accept_rate": _mean_sched("curator_accept_rate"),
            "curator_reject_rate": _mean_sched("curator_reject_rate"),
            "total_procedural_memories": total_memories,
            "provided_tools": tools,
            "episodes": episode_results,
        }
        return summary

    @staticmethod
    def _serialize_curation_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for item in actions:
            action = item.get("action")
            action_value = action.value if hasattr(action, "value") else str(action)
            serialized.append(
                {
                    "action": action_value,
                    "memory_id": str(item.get("memory_id") or ""),
                    "reason": str(item.get("reason") or ""),
                    "accepted": bool(item.get("accepted", False)),
                }
            )
        return serialized

    @staticmethod
    def _write_validation_report(metrics: dict[str, Any], run_dir: Path) -> None:
        rows: list[dict[str, Any]] = []
        for variant, data in metrics.items():
            row = {"variant": variant}
            for field in _VALIDATION_FIELDS:
                row[field] = data.get(field, 0.0)
            rows.append(row)

        csv_out = run_dir / "validation_metrics_report.csv"
        md_out = run_dir / "validation_metrics_report.md"

        with csv_out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["variant", *_VALIDATION_FIELDS])
            writer.writeheader()
            writer.writerows(rows)

        headers = ["Variant", *[f.replace("_", " ") for f in _VALIDATION_FIELDS]]
        lines: list[str] = []
        lines.append("# Validation Metrics Report")
        lines.append("")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows:
            values = [str(row["variant"])]
            for field in _VALIDATION_FIELDS:
                value = row.get(field, 0.0)
                values.append(f"{float(value):.3f}" if isinstance(value, (int, float)) else str(value))
            lines.append("| " + " | ".join(values) + " |")
        lines.append("")
        md_out.write_text("\n".join(lines), encoding="utf-8")
