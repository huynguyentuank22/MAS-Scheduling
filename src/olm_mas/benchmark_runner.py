"""Synthetic benchmark runner with ablation support.

Generates recurring task episodes with hard orchestration traps,
runs them across experiment variants, and produces comparison metrics.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

import yaml

from .agent_registry import AgentRegistry
from .agent_runtime import AgentRuntime
from .blackboard import Blackboard
from .evaluator import SchedulingEvaluator
from .memory_curator import MemoryCurator
from .memory_store import MemoryStore
from .orchestrator import Orchestrator
from .policy_engine import PolicyEngine
from .schemas import MemoryStatus, ProceduralControlMemory
from .synthetic_benchmark import SYNTHETIC_TASK_FAMILIES, get_seed_memories
from .trace_logger import TraceLogger


TASK_FAMILIES: dict[str, dict[str, Any]] = SYNTHETIC_TASK_FAMILIES

HARD_FAMILIES = {
    "evidence_based_writing",
    "multi_source_conflict",
    "form_submission",
    "debugging",
    "dynamic_recovery",
}


def generate_episodes(
    num_episodes: int,
    seed: int = 42,
    hard_family_ratio: float = 0.65,
) -> list[dict[str, Any]]:
    """Generate a sequence of synthetic task episodes."""
    rng = random.Random(seed)
    all_families = list(TASK_FAMILIES.keys())
    hard_families = [f for f in all_families if f in HARD_FAMILIES]
    soft_families = [f for f in all_families if f not in HARD_FAMILIES]
    episodes: list[dict[str, Any]] = []

    for i in range(num_episodes):
        choose_hard = bool(hard_families and rng.random() < hard_family_ratio)
        family_name = rng.choice(hard_families if choose_hard else soft_families)
        family = TASK_FAMILIES[family_name]

        suffix = f" (episode {i + 1})"
        tasks = [t + suffix for t in family["tasks"]]

        episodes.append(
            {
                "episode_idx": i,
                "task_family": family_name,
                "objective": family["objective"] + suffix,
                "tasks": tasks,
                "difficulty": family.get("difficulty", 0.5),
            }
        )

    return episodes


class BenchmarkRunner:
    """Runs a synthetic benchmark with multiple experiment variants."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        output_dir: str = "experiments",
    ) -> None:
        self._config: dict[str, Any] = {}
        self._output_dir = output_dir
        if config_path:
            self._config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))

    def run(self) -> dict[str, Any]:
        """Run all enabled experiment variants and produce comparison."""
        exp_cfg = self._config.get("experiment", {})
        num_episodes = exp_cfg.get("num_episodes", 50)
        seed = exp_cfg.get("random_seed", 42)
        hard_family_ratio = exp_cfg.get("hard_family_ratio", 0.65)
        split = exp_cfg.get("split", {})
        accumulation = split.get("accumulation", int(num_episodes * 0.6))
        test_start = accumulation

        variants_cfg = self._config.get("variants", {})
        episodes = generate_episodes(num_episodes, seed, hard_family_ratio=hard_family_ratio)

        results: dict[str, Any] = {}

        for variant_name, variant_cfg in variants_cfg.items():
            if not variant_cfg.get("enabled", False):
                continue
            print(f"\n{'=' * 60}")
            print(f"Running variant: {variant_name}")
            print(f"{'=' * 60}")

            variant_result = self._run_variant(
                variant_name=variant_name,
                variant_cfg=variant_cfg,
                episodes=episodes,
                seed=seed,
                test_start=test_start,
            )
            results[variant_name] = variant_result

        comparison = self._compare(results)

        os.makedirs(self._output_dir, exist_ok=True)
        metrics_path = Path(self._output_dir) / "metrics.json"
        metrics_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        comparison_path = Path(self._output_dir) / "comparison_report.json"
        comparison_path.write_text(json.dumps(comparison, indent=2, default=str), encoding="utf-8")

        print(f"\nMetrics saved to {metrics_path}")
        print(f"Comparison saved to {comparison_path}")

        return {"results": results, "comparison": comparison}

    def _run_variant(
        self,
        variant_name: str,
        variant_cfg: dict,
        episodes: list[dict],
        seed: int,
        test_start: int,
    ) -> dict[str, Any]:
        """Run all episodes for a single variant."""
        use_memory = variant_cfg.get("orchestrator_local_memory", False)
        use_curation = variant_cfg.get("memory_curation", False)
        memory_source = str(variant_cfg.get("memory_source", "curated"))
        seed_memories = bool(variant_cfg.get("seed_memories", use_memory))

        trace_dir = str(Path(self._output_dir) / "traces" / variant_name)
        memory_dir = str(Path(self._output_dir) / "memories" / variant_name)

        registry = AgentRegistry()
        runtime = AgentRuntime(seed=seed, failure_rate=0.25)
        memory_store = MemoryStore(memory_dir=memory_dir if use_memory else None)
        blackboard = Blackboard()
        policy_engine = PolicyEngine()
        trace_logger = TraceLogger(trace_dir=trace_dir)
        evaluator = SchedulingEvaluator()
        curator = MemoryCurator(memory_store) if use_curation else None

        if use_memory and seed_memories:
            self._seed_variant_memories(
                memory_store=memory_store,
                memory_source=memory_source,
                seed=seed,
            )

        orchestrator = Orchestrator(
            registry=registry,
            runtime=runtime,
            memory_store=memory_store,
            blackboard=blackboard,
            policy_engine=policy_engine,
            trace_logger=trace_logger,
            evaluator=evaluator,
            curator=curator,
            use_memory=use_memory,
        )

        episode_results: list[dict[str, Any]] = []
        accumulation_scores: list[float] = []
        test_scores: list[float] = []

        for ep in episodes:
            result = orchestrator.run_episode(
                objective=ep["objective"],
                task_descriptions=ep["tasks"],
                benchmark_name="synthetic",
                task_family=ep["task_family"],
            )

            ev = result["evaluation"]
            ep_summary = {
                "episode_idx": ep["episode_idx"],
                "task_family": ep["task_family"],
                "benchmark_success": ev.benchmark_success,
                "benchmark_score": ev.benchmark_score,
                "scheduling_scores": ev.scheduling_scores,
                "memory_used": len(ev.memory_used),
                "curation_actions": [(a.value, mid) for a, mid in result["curation_actions"]],
            }
            episode_results.append(ep_summary)

            if ep["episode_idx"] < test_start:
                accumulation_scores.append(ev.benchmark_score)
            else:
                test_scores.append(ev.benchmark_score)

            status = "OK" if ev.benchmark_success else "FAIL"
            print(
                f"  Episode {ep['episode_idx'] + 1:3d} | "
                f"{ep['task_family']:24s} | "
                f"{status:4s} | "
                f"score={ev.benchmark_score:.2f} | "
                f"mem_used={len(ev.memory_used)}"
            )

        all_scores = [e["benchmark_score"] for e in episode_results]
        success_count = sum(1 for e in episode_results if e["benchmark_success"])
        total_memories = len(memory_store.list_procedural())

        def _mean_sched(metric_name: str) -> float:
            values = [float(e["scheduling_scores"].get(metric_name, 0.0)) for e in episode_results]
            return round(sum(values) / max(len(values), 1), 3)

        def _sum_sched(metric_name: str) -> int:
            return int(sum(int(e["scheduling_scores"].get(metric_name, 0)) for e in episode_results))

        variant_summary = {
            "variant": variant_name,
            "total_episodes": len(episodes),
            "success_count": success_count,
            "success_rate": round(success_count / max(len(episodes), 1), 3),
            "mean_score": round(sum(all_scores) / max(len(all_scores), 1), 3),
            "accumulation_mean_score": (
                round(sum(accumulation_scores) / max(len(accumulation_scores), 1), 3)
                if accumulation_scores
                else 0.0
            ),
            "test_mean_score": (
                round(sum(test_scores) / max(len(test_scores), 1), 3)
                if test_scores
                else 0.0
            ),
            "dependency_violation_rate": _mean_sched("dependency_violation_rate"),
            "order_violation_rate": _mean_sched("order_violation_rate"),
            "missing_required_agent_rate": _mean_sched("missing_required_agent_rate"),
            "recovery_success_rate": _mean_sched("recovery_success_rate"),
            "unnecessary_agent_calls": _mean_sched("unnecessary_agent_calls"),
            "memory_changed_scheduling_decisions": _sum_sched("memory_changed_scheduling_decisions"),
            "support_only_count": _sum_sched("support_only_count"),
            "changed_agent_selection_count": _sum_sched("changed_agent_selection_count"),
            "changed_ordering_count": _sum_sched("changed_ordering_count"),
            "changed_recovery_count": _sum_sched("changed_recovery_count"),
            "total_procedural_memories": total_memories,
            "episodes": episode_results,
        }

        return variant_summary

    def _seed_variant_memories(
        self,
        memory_store: MemoryStore,
        memory_source: str,
        seed: int,
    ) -> None:
        for mem in self.build_seed_memories(memory_source=memory_source, seed=seed):
            memory_store.put_procedural(mem)

    @staticmethod
    def build_seed_memories(
        memory_source: str,
        seed: int,
    ) -> list[ProceduralControlMemory]:
        seed_defs = get_seed_memories()
        families = list(seed_defs.keys())

        if memory_source in {"shuffled", "shuffled_or_random", "random"}:
            rng = random.Random(seed)
            shuffled_targets = families[:]
            rng.shuffle(shuffled_targets)
            if shuffled_targets == families:
                shuffled_targets = shuffled_targets[1:] + shuffled_targets[:1]
            mapping = dict(zip(families, shuffled_targets))
        else:
            mapping = {family: family for family in families}

        out: list[ProceduralControlMemory] = []
        for source_family in families:
            payload = dict(seed_defs[source_family])
            target_family = mapping[source_family]
            trigger = dict(payload.get("trigger", {}))
            trigger["task_family"] = target_family
            trigger["source_family"] = source_family
            payload["trigger"] = trigger

            mem = ProceduralControlMemory(
                trigger=payload.get("trigger", {}),
                recommended_schedule=list(payload.get("recommended_schedule", [])),
                avoid=list(payload.get("avoid", [])),
                recommended_recovery=list(payload.get("recommended_recovery", [])),
                confidence=float(payload.get("confidence", 0.75)),
                status=MemoryStatus.ACTIVE,
                supporting_episodes=["seeded"],
            )
            out.append(mem)

        return out

    @staticmethod
    def _compare(results: dict[str, Any]) -> dict[str, Any]:
        """Produce a side-by-side comparison of variants."""
        comparison: dict[str, Any] = {"variants": {}, "delta_vs_no_memory": {}}

        summary_fields = [
            "success_rate",
            "mean_score",
            "accumulation_mean_score",
            "test_mean_score",
            "dependency_violation_rate",
            "order_violation_rate",
            "missing_required_agent_rate",
            "recovery_success_rate",
            "unnecessary_agent_calls",
            "memory_changed_scheduling_decisions",
            "support_only_count",
            "changed_agent_selection_count",
            "changed_ordering_count",
            "changed_recovery_count",
            "total_procedural_memories",
        ]

        for name, data in results.items():
            comparison["variants"][name] = {field: data.get(field) for field in summary_fields}

        if "mas_no_memory" in results:
            base = results["mas_no_memory"]
            for name, data in results.items():
                if name == "mas_no_memory":
                    continue
                comparison["delta_vs_no_memory"][name] = {
                    "success_rate_improvement": round(data["success_rate"] - base["success_rate"], 3),
                    "mean_score_improvement": round(data["mean_score"] - base["mean_score"], 3),
                    "order_violation_rate_reduction": round(
                        base["order_violation_rate"] - data["order_violation_rate"],
                        3,
                    ),
                    "missing_required_agent_rate_reduction": round(
                        base["missing_required_agent_rate"] - data["missing_required_agent_rate"],
                        3,
                    ),
                }

            # Backward-compatible summary for the main memory variant.
            if "mas_orchestrator_memory" in results:
                mem = results["mas_orchestrator_memory"]
                comparison["delta"] = {
                    "success_rate_improvement": round(mem["success_rate"] - base["success_rate"], 3),
                    "mean_score_improvement": round(mem["mean_score"] - base["mean_score"], 3),
                    "test_score_improvement": round(mem["test_mean_score"] - base["test_mean_score"], 3),
                }

        return comparison
