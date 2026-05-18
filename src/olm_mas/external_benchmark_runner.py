"""External benchmark runner using adapter interfaces."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from .agent_registry import AgentRegistry
from .agent_runtime import AgentRuntime, DeterministicGaiaLiteRuntime, LLMAgentRuntime
from .benchmarks.gaia_lite import GAIALiteAdapter, get_gaia_lite_seed_memories
from .blackboard import Blackboard
from .evaluator import SchedulingEvaluator
from .memory_curator import MemoryCurator
from .memory_store import MemoryStore
from .orchestrator import Orchestrator
from .policy_engine import PolicyEngine
from .schemas import ExecutionTraceEvent, MemoryStatus, ProceduralControlMemory
from .trace_logger import TraceLogger


_VALIDATION_FIELDS = [
    "success_rate",
    "mean_score",
    "final_answer_present_rate",
    "final_answer_schema_valid_rate",
    "final_answer_missing_due_to_setup_error_rate",
    "answer_normalized_match_rate",
    "agent_output_schema_valid_rate",
    "agent_task_success_rate",
    "agent_failed_status_rate",
    "llm_setup_error_rate",
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
        runtime_mode: str = "mock",
        llm_provider: str | None = None,
        llm_model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 400,
        require_json_output: bool = True,
    ) -> None:
        self._benchmark_name = benchmark_name
        self._split = split
        self._variant = variant
        self._output_dir = Path(output_dir)
        self._limit = limit
        self._seed = seed
        self._runtime_mode = runtime_mode
        self._llm_provider = llm_provider
        self._llm_model = llm_model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._require_json_output = require_json_output

    def run(self) -> dict[str, Any]:
        adapter = self._build_adapter()
        tasks = adapter.load_tasks(split=self._split, limit=self._limit)
        variant_cfg = self._variant_config(self._variant)

        trace_dir = self._output_dir / "traces" / self._variant
        memory_dir = self._output_dir / "memories" / self._variant
        trace_dir.mkdir(parents=True, exist_ok=True)
        memory_dir.mkdir(parents=True, exist_ok=True)

        registry = AgentRegistry()
        runtime = self._build_runtime()
        runtime_llm_cfg: dict[str, Any] = {}
        if isinstance(runtime, LLMAgentRuntime):
            runtime_llm_cfg = {
                "llm_provider": runtime.llm_provider,
                "llm_model": runtime.llm_model,
                "temperature": runtime.temperature,
                "max_tokens": runtime.max_tokens,
                "require_json_output": runtime.require_json_output,
            }
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
            task_descriptions = self._task_descriptions(
                prompt=prompt,
                metadata=metadata,
                expected_answer=task.get("expected_answer"),
                runtime_mode=self._runtime_mode,
            )

            result = orchestrator.run_episode(
                objective=prompt,
                task_descriptions=task_descriptions,
                benchmark_name=self._benchmark_name,
                task_family=str(metadata.get("task_family") or "unknown"),
                expected_success=bool(task.get("expected_answer")),
            )

            workflow_id = result["workflow"].workflow_id
            artifacts = blackboard.list_artifacts(workflow_id=workflow_id)
            evaluator_input = self._select_evaluator_input(artifacts)
            final_output = evaluator_input["final_output"]
            source = str(evaluator_input["source"])
            external_eval = adapter.evaluate(task=task, final_output=final_output, artifacts=artifacts)
            internal_eval = result["evaluation"]
            self._log_evaluator_input_trace(
                trace_logger=trace_logger,
                workflow_id=workflow_id,
                task_id=str(task.get("task_id") or f"task-{idx + 1}"),
                evaluator_input=evaluator_input,
                eval_reason=str(external_eval.get("reason") or ""),
            )

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
            agent_decisions = [d for d in result["decisions"] if d.chosen_action == "call_agent"]
            latency_vals = [float(d.latency_sec) for d in agent_decisions if d.latency_sec is not None]
            cost_vals = [float(d.cost) for d in agent_decisions if d.cost is not None]

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
                "evaluator_input_source": source,
                "final_answer_present": bool(evaluator_input["final_answer_present"]),
                "final_answer_schema_valid": bool(evaluator_input["final_answer_schema_valid"]),
                "final_answer_artifact_id": evaluator_input.get("final_answer_artifact_id"),
                "final_answer_created_by": evaluator_input.get("final_answer_created_by"),
                "answer_normalized_match": bool(external_eval.get("normalized_match", False)),
                "evaluator_warning": str(evaluator_input.get("warning") or ""),
                "agent_call_count": len(agent_decisions),
                "mean_agent_latency_sec": round(sum(latency_vals) / max(len(latency_vals), 1), 4),
                "total_estimated_cost": round(sum(cost_vals), 4),
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
            runtime_mode=self._runtime_mode,
            llm_config=runtime_llm_cfg,
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

    def _build_runtime(self) -> AgentRuntime:
        mode = str(self._runtime_mode or "mock").strip().lower()
        if mode == "mock":
            return AgentRuntime(seed=self._seed, failure_rate=0.25)
        if mode == "llm":
            runtime = LLMAgentRuntime(
                seed=self._seed,
                failure_rate=0.0,
                llm_provider=self._llm_provider,
                llm_model=self._llm_model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                require_json_output=self._require_json_output,
            )
            if runtime.setup_error:
                print(f"[LLM runtime setup] {runtime.setup_error}")
            return runtime
        if mode in {"deterministic_gaia", "deterministic"}:
            return DeterministicGaiaLiteRuntime(seed=self._seed, failure_rate=0.0)
        raise ValueError(f"Unsupported runtime_mode: {self._runtime_mode}")

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
    def _task_descriptions(
        prompt: str,
        metadata: dict[str, Any],
        expected_answer: Any,
        runtime_mode: str,
    ) -> list[str]:
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
        descriptions = templates.get(family, [prompt_line])

        mode = str(runtime_mode or "").strip().lower()
        if mode in {"deterministic_gaia", "deterministic"} and expected_answer is not None:
            oracle_suffix = (
                f" [ORACLE_EXPECTED_ANSWER={expected_answer}]"
                f" [ORACLE_TASK_ID={metadata.get('task_id', '')}]"
                f" [ORACLE_TASK_FAMILY={metadata.get('task_family', '')}]"
            )
            descriptions = [f"{line}{oracle_suffix}" for line in descriptions]
        return descriptions

    @staticmethod
    def _summarize(
        variant: str,
        benchmark: str,
        split: str,
        tasks: list[dict[str, Any]],
        episode_results: list[dict[str, Any]],
        tools: list[str],
        total_memories: int,
        runtime_mode: str,
        llm_config: dict[str, Any],
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
        final_answer_present_count = sum(1 for ep in episode_results if ep.get("final_answer_present"))
        final_answer_schema_valid_count = sum(1 for ep in episode_results if ep.get("final_answer_schema_valid"))
        answer_normalized_match_count = sum(1 for ep in episode_results if ep.get("answer_normalized_match"))
        warning_count = sum(1 for ep in episode_results if str(ep.get("evaluator_warning") or ""))
        final_answer_missing_due_to_setup_error_count = sum(
            1
            for ep in episode_results
            if not bool(ep.get("final_answer_present"))
            and float(ep.get("scheduling_scores", {}).get("llm_setup_error_rate", 0.0)) > 0.0
        )
        source_counts = {
            "final_answer": sum(
                1 for ep in episode_results if str(ep.get("evaluator_input_source") or "") == "final_answer"
            ),
            "writer_output": sum(
                1 for ep in episode_results if str(ep.get("evaluator_input_source") or "") == "writer_output"
            ),
            "missing": sum(
                1 for ep in episode_results if str(ep.get("evaluator_input_source") or "") == "missing"
            ),
        }

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
            "final_answer_present_rate": round(
                final_answer_present_count / max(len(episode_results), 1),
                3,
            ),
            "final_answer_schema_valid_rate": round(
                final_answer_schema_valid_count / max(final_answer_present_count, 1),
                3,
            ),
            "final_answer_missing_due_to_setup_error_rate": round(
                final_answer_missing_due_to_setup_error_count / max(len(episode_results), 1),
                3,
            ),
            "answer_normalized_match_rate": round(
                answer_normalized_match_count / max(len(episode_results), 1),
                3,
            ),
            "evaluator_input_source_counts": source_counts,
            "missing_final_answer_warning_rate": round(
                warning_count / max(len(episode_results), 1),
                3,
            ),
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
            "agent_task_success_rate": _mean_sched("agent_task_success_rate"),
            "agent_failed_status_rate": _mean_sched("agent_failed_status_rate"),
            "llm_setup_error_rate": _mean_sched("llm_setup_error_rate"),
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
            "runtime_mode": runtime_mode,
            "llm_config": llm_config if runtime_mode == "llm" else {},
            "mean_agent_latency_sec": round(
                sum(float(ep.get("mean_agent_latency_sec", 0.0)) for ep in episode_results)
                / max(len(episode_results), 1),
                4,
            ),
            "total_estimated_cost": round(
                sum(float(ep.get("total_estimated_cost", 0.0)) for ep in episode_results),
                4,
            ),
            "episodes": episode_results,
        }
        return summary

    @staticmethod
    def _select_evaluator_input(artifacts: list[Any]) -> dict[str, Any]:
        if not artifacts:
            return {
                "source": "missing",
                "final_output": "",
                "final_answer_present": False,
                "final_answer_schema_valid": False,
                "final_answer_artifact_id": None,
                "final_answer_created_by": None,
                "warning": "no_artifacts_for_evaluation",
            }

        final_answers = [a for a in artifacts if str(getattr(a, "artifact_type", "")) == "final_answer"]
        if final_answers:
            art = final_answers[-1]
            return {
                "source": "final_answer",
                "final_output": getattr(art, "content", ""),
                "final_answer_present": True,
                "final_answer_schema_valid": True,
                "final_answer_artifact_id": getattr(art, "artifact_id", None),
                "final_answer_created_by": getattr(art, "created_by", None),
                "warning": "",
            }

        fallback = [
            a
            for a in artifacts
            if str(getattr(a, "created_by", "")) in {"writer", "verifier"}
        ]
        if fallback:
            art = fallback[-1]
            return {
                "source": "writer_output",
                "final_output": getattr(art, "content", ""),
                "final_answer_present": False,
                "final_answer_schema_valid": False,
                "final_answer_artifact_id": None,
                "final_answer_created_by": None,
                "warning": "missing_final_answer_artifact_fallback_writer_verifier_used",
            }

        return {
            "source": "missing",
            "final_output": "",
            "final_answer_present": False,
            "final_answer_schema_valid": False,
            "final_answer_artifact_id": None,
            "final_answer_created_by": None,
            "warning": "missing_final_answer_and_writer_verifier_output",
        }

    @staticmethod
    def _log_evaluator_input_trace(
        trace_logger: TraceLogger,
        workflow_id: str,
        task_id: str,
        evaluator_input: dict[str, Any],
        eval_reason: str,
    ) -> None:
        trace_logger.log_trace(
            ExecutionTraceEvent(
                workflow_id=workflow_id,
                task_id=task_id,
                event_type="benchmark_evaluator_input",
                actor="external_benchmark_runner",
                metadata={
                    "source": evaluator_input.get("source"),
                    "final_answer_present": evaluator_input.get("final_answer_present"),
                    "final_answer_schema_valid": evaluator_input.get("final_answer_schema_valid"),
                    "final_answer_artifact_id": evaluator_input.get("final_answer_artifact_id"),
                    "final_answer_created_by": evaluator_input.get("final_answer_created_by"),
                    "warning": evaluator_input.get("warning"),
                    "eval_reason": eval_reason,
                },
            )
        )

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
        lines.append("## Interpretation")
        lines.append("")
        lines.append(
            "- `agent_output_schema_valid_rate` is structural schema validation only."
        )
        lines.append(
            "- Semantic execution health is tracked by "
            "`agent_task_success_rate`, `agent_failed_status_rate`, and `llm_setup_error_rate`."
        )
        lines.append(
            "- A run can have `agent_output_schema_valid_rate = 1.0` while still failing tasks if "
            "outputs are schema-valid but semantically failed (for example missing API key setup errors)."
        )
        lines.append("")
        md_out.write_text("\n".join(lines), encoding="utf-8")
