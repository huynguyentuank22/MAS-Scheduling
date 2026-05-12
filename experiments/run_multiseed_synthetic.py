#!/usr/bin/env python
"""Run multi-seed synthetic benchmark and summarize stability metrics."""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from olm_mas.benchmark_runner import BenchmarkRunner


SEEDS = [0, 1, 2, 3, 4]
VARIANTS = [
    "mas_no_memory",
    "mas_orchestrator_memory",
    "mas_shuffled_memory",
    "mas_random_memory",
]
METRIC_KEYS = [
    "success_rate",
    "mean_score",
    "order_violation_rate",
    "missing_required_agent_rate",
    "memory_changed_scheduling_decisions",
    "eligible_count",
    "blocked_count",
    "curator_accept_rate",
    "curator_reject_rate",
]


@dataclass
class SeedVariantRow:
    seed: int
    variant: str
    success_rate: float
    mean_score: float
    order_violation_rate: float
    missing_required_agent_rate: float
    memory_changed_scheduling_decisions: float
    eligible_count: float
    blocked_count: float
    curator_accept_rate: float
    curator_reject_rate: float


def _make_config(seed: int) -> dict[str, Any]:
    return {
        "experiment": {
            "name": f"multiseed_synthetic_seed_{seed}",
            "benchmark": "synthetic",
            "num_episodes": 100,
            "hard_family_ratio": 0.7,
            "split": {"accumulation": 60, "test": 40},
            "random_seed": seed,
        },
        "variants": {
            "mas_no_memory": {
                "enabled": True,
                "orchestrator_local_memory": False,
                "blackboard": True,
                "memory_curation": False,
                "policy_engine": True,
            },
            "mas_orchestrator_memory": {
                "enabled": True,
                "orchestrator_local_memory": True,
                "blackboard": True,
                "memory_curation": True,
                "policy_engine": True,
                "seed_memories": True,
                "memory_source": "curated",
            },
            "mas_shuffled_memory": {
                "enabled": True,
                "orchestrator_local_memory": True,
                "memory_source": "shuffled",
                "seed_memories": True,
                "blackboard": True,
                "memory_curation": False,
                "policy_engine": True,
            },
            "mas_random_memory": {
                "enabled": True,
                "orchestrator_local_memory": True,
                "memory_source": "random",
                "seed_memories": True,
                "blackboard": True,
                "memory_curation": False,
                "policy_engine": True,
            },
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _count_memory_eligibility(trace_dir: Path) -> tuple[int, int, int]:
    retrieved = 0
    eligible = 0
    blocked = 0
    if not trace_dir.exists():
        return retrieved, eligible, blocked

    for trace_file in trace_dir.glob("*.jsonl"):
        for record in _read_jsonl(trace_file):
            if record.get("_type") != "DecisionEvent":
                continue
            if record.get("chosen_action") != "retrieve_memory":
                continue
            influence = dict(record.get("memory_influence") or {})
            retrieved += 1
            if bool(influence.get("eligible_to_influence", False)):
                eligible += 1
            if influence.get("blocked_reason"):
                blocked += 1
    return retrieved, eligible, blocked


def _to_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _row_to_dict(section: str, row: SeedVariantRow) -> dict[str, Any]:
    return {
        "section": section,
        "seed": row.seed,
        "variant": row.variant,
        "success_rate": row.success_rate,
        "mean_score": row.mean_score,
        "order_violation_rate": row.order_violation_rate,
        "missing_required_agent_rate": row.missing_required_agent_rate,
        "memory_changed_scheduling_decisions": row.memory_changed_scheduling_decisions,
        "eligible_count": row.eligible_count,
        "blocked_count": row.blocked_count,
        "curator_accept_rate": row.curator_accept_rate,
        "curator_reject_rate": row.curator_reject_rate,
    }


def _format_mean_std(values: list[float]) -> str:
    if not values:
        return "0.000 +/- 0.000"
    mean_val = statistics.mean(values)
    std_val = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{mean_val:.3f} +/- {std_val:.3f}"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def _compare_seedwise(
    data: dict[str, list[SeedVariantRow]],
    left: str,
    right: str,
    metric: str,
) -> tuple[int, int, int]:
    wins = ties = losses = 0
    by_seed_right = {row.seed: row for row in data.get(right, [])}
    for row_left in data.get(left, []):
        row_right = by_seed_right.get(row_left.seed)
        if row_right is None:
            continue
        lv = _to_float(getattr(row_left, metric))
        rv = _to_float(getattr(row_right, metric))
        if lv > rv:
            wins += 1
        elif lv < rv:
            losses += 1
        else:
            ties += 1
    return wins, ties, losses


def main() -> None:
    experiments_dir = Path("experiments")
    run_root = experiments_dir / "multiseed_runs"
    run_root.mkdir(parents=True, exist_ok=True)

    per_seed_rows: list[SeedVariantRow] = []

    for seed in SEEDS:
        cfg = _make_config(seed=seed)
        cfg_path = run_root / f"config_seed_{seed}.yaml"
        out_dir = run_root / f"seed_{seed}"
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

        runner = BenchmarkRunner(config_path=cfg_path, output_dir=str(out_dir))
        runner.run()

        metrics = _read_json(out_dir / "metrics.json")
        for variant in VARIANTS:
            summary = metrics.get(variant)
            if not summary:
                continue
            _retrieved, eligible, blocked = _count_memory_eligibility(out_dir / "traces" / variant)
            per_seed_rows.append(
                SeedVariantRow(
                    seed=seed,
                    variant=variant,
                    success_rate=_to_float(summary.get("success_rate")),
                    mean_score=_to_float(summary.get("mean_score")),
                    order_violation_rate=_to_float(summary.get("order_violation_rate")),
                    missing_required_agent_rate=_to_float(summary.get("missing_required_agent_rate")),
                    memory_changed_scheduling_decisions=_to_float(
                        summary.get("memory_changed_scheduling_decisions")
                    ),
                    eligible_count=float(eligible),
                    blocked_count=float(blocked),
                    curator_accept_rate=_to_float(summary.get("curator_accept_rate")),
                    curator_reject_rate=_to_float(summary.get("curator_reject_rate")),
                )
            )

    by_variant: dict[str, list[SeedVariantRow]] = {v: [] for v in VARIANTS}
    for row in per_seed_rows:
        by_variant[row.variant].append(row)

    csv_rows: list[dict[str, Any]] = []
    for row in per_seed_rows:
        csv_rows.append(_row_to_dict("per_seed", row))

    aggregate_rows: dict[str, dict[str, str]] = {}
    for variant in VARIANTS:
        rows = by_variant.get(variant, [])
        metric_values = {
            key: [_to_float(getattr(row, key)) for row in rows]
            for key in METRIC_KEYS
        }
        aggregate_rows[variant] = {
            key: _format_mean_std(metric_values[key])
            for key in METRIC_KEYS
        }
        csv_rows.append(
            {
                "section": "aggregate_mean_std",
                "seed": "all",
                "variant": variant,
                **aggregate_rows[variant],
            }
        )

    csv_out = experiments_dir / "multiseed_synthetic_summary.csv"
    fields = list(csv_rows[0].keys())
    with csv_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)

    headers = [
        "Variant",
        "Success Rate",
        "Mean Score",
        "Order Viol.",
        "Missing Req.",
        "Mem Changed",
        "Eligible",
        "Blocked",
        "Curator Accept",
        "Curator Reject",
    ]
    md_rows: list[list[Any]] = []
    for variant in VARIANTS:
        agg = aggregate_rows[variant]
        md_rows.append(
            [
                variant,
                agg["success_rate"],
                agg["mean_score"],
                agg["order_violation_rate"],
                agg["missing_required_agent_rate"],
                agg["memory_changed_scheduling_decisions"],
                agg["eligible_count"],
                agg["blocked_count"],
                agg["curator_accept_rate"],
                agg["curator_reject_rate"],
            ]
        )

    orch_vs_no_score = _compare_seedwise(by_variant, "mas_orchestrator_memory", "mas_no_memory", "mean_score")
    orch_vs_no_success = _compare_seedwise(by_variant, "mas_orchestrator_memory", "mas_no_memory", "success_rate")
    orch_vs_shuf_score = _compare_seedwise(by_variant, "mas_orchestrator_memory", "mas_shuffled_memory", "mean_score")
    orch_vs_rand_score = _compare_seedwise(by_variant, "mas_orchestrator_memory", "mas_random_memory", "mean_score")
    shuf_vs_orch_score = _compare_seedwise(by_variant, "mas_shuffled_memory", "mas_orchestrator_memory", "mean_score")

    orch_better_than_no_consistent = (
        orch_vs_no_score[2] == 0 and orch_vs_no_success[2] == 0 and orch_vs_no_score[0] > 0
    )
    orch_better_than_shuf_consistent = orch_vs_shuf_score[2] == 0 and orch_vs_shuf_score[0] > 0
    orch_better_than_rand_consistent = orch_vs_rand_score[2] == 0 and orch_vs_rand_score[0] > 0
    shuffled_advantage_is_single_seed = shuf_vs_orch_score[0] <= 1

    md_lines: list[str] = []
    md_lines.append("# Multi-Seed Synthetic Summary")
    md_lines.append("")
    md_lines.append("- Seeds: 0, 1, 2, 3, 4")
    md_lines.append("- Episodes per seed: 100")
    md_lines.append("- Variants: mas_no_memory, mas_orchestrator_memory, mas_shuffled_memory, mas_random_memory")
    md_lines.append("")
    md_lines.append("## Aggregate Metrics (mean +/- std)")
    md_lines.append("")
    md_lines.append(_table(headers, md_rows))
    md_lines.append("")
    md_lines.append("## Seedwise Comparison Diagnostics")
    md_lines.append("")
    md_lines.append(
        f"- Orchestrator vs no-memory (mean_score): wins/ties/losses = {orch_vs_no_score[0]}/{orch_vs_no_score[1]}/{orch_vs_no_score[2]}"
    )
    md_lines.append(
        f"- Orchestrator vs no-memory (success_rate): wins/ties/losses = {orch_vs_no_success[0]}/{orch_vs_no_success[1]}/{orch_vs_no_success[2]}"
    )
    md_lines.append(
        f"- Orchestrator vs shuffled (mean_score): wins/ties/losses = {orch_vs_shuf_score[0]}/{orch_vs_shuf_score[1]}/{orch_vs_shuf_score[2]}"
    )
    md_lines.append(
        f"- Orchestrator vs random (mean_score): wins/ties/losses = {orch_vs_rand_score[0]}/{orch_vs_rand_score[1]}/{orch_vs_rand_score[2]}"
    )
    md_lines.append("")
    md_lines.append("## Answers")
    md_lines.append("")
    md_lines.append("1. Is orchestrator memory consistently better than no-memory?")
    md_lines.append(
        f"- {'Yes' if orch_better_than_no_consistent else 'No'} (based on seedwise mean_score and success_rate comparisons)."
    )
    md_lines.append("")
    md_lines.append("2. Is orchestrator memory consistently better than shuffled/random memory?")
    md_lines.append(
        f"- Shuffled: {'Yes' if orch_better_than_shuf_consistent else 'No'}; Random: {'Yes' if orch_better_than_rand_consistent else 'No'}."
    )
    md_lines.append("")
    md_lines.append("3. Is the remaining shuffled advantage just single-seed noise?")
    md_lines.append(
        f"- {'Yes' if shuffled_advantage_is_single_seed else 'No'} (shuffled beats orchestrator in {shuf_vs_orch_score[0]} seed(s))."
    )
    md_lines.append("")
    md_lines.append("4. Is synthetic benchmark ready to freeze?")
    freeze_ready = orch_better_than_no_consistent and shuffled_advantage_is_single_seed
    md_lines.append(
        f"- {'Yes' if freeze_ready else 'Not yet'} (use this with your domain judgment on robustness and external validity)."
    )
    md_lines.append("")

    md_out = experiments_dir / "multiseed_synthetic_summary.md"
    md_out.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"Wrote CSV: {csv_out}")
    print(f"Wrote Markdown: {md_out}")


if __name__ == "__main__":
    main()
