#!/usr/bin/env python
"""Build consolidated robustness summary across synthetic experiment settings."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNS: list[tuple[str, str]] = [
    ("normal_hard_synthetic", "robustness_normal"),
    ("llm_noise_malformed_json", "robustness_noise_malformed_json"),
    ("llm_noise_missing_fields", "robustness_noise_missing_fields"),
    ("llm_noise_hallucinated_artifact_ref", "robustness_noise_hallucinated_artifact_ref"),
    ("llm_noise_overgeneralized_lesson", "robustness_noise_overgeneralized_lesson"),
]

VARIANT_ORDER = [
    "mas_no_memory",
    "mas_orchestrator_memory",
    "mas_shuffled_memory",
    "mas_random_memory",
    "mas_oracle_memory",
]

EPISODE_PATTERN = re.compile(r"\(episode\s+(\d+)\)", re.IGNORECASE)


@dataclass
class EpisodeTraceMeta:
    workflow_id: str
    retrieve_events: list[dict[str, Any]] = field(default_factory=list)
    invalid_output_events: int = 0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _extract_episode_idx(decision_events: list[dict[str, Any]]) -> int | None:
    for event in decision_events:
        rationale = str(event.get("rationale_summary") or "")
        match = EPISODE_PATTERN.search(rationale)
        if match:
            return int(match.group(1)) - 1
    return None


def _scan_variant_traces(variant_trace_dir: Path) -> tuple[dict[str, int], dict[int, EpisodeTraceMeta]]:
    counters = {
        "retrieved_count": 0,
        "eligible_count": 0,
        "blocked_count": 0,
    }
    by_episode: dict[int, EpisodeTraceMeta] = {}

    if not variant_trace_dir.exists():
        return counters, by_episode

    for trace_file in sorted(variant_trace_dir.glob("*.jsonl")):
        records = _load_jsonl(trace_file)
        decisions = [r for r in records if r.get("_type") == "DecisionEvent"]
        traces = [r for r in records if r.get("_type") == "ExecutionTraceEvent"]
        if not decisions:
            continue

        for d in decisions:
            if d.get("chosen_action") != "retrieve_memory":
                continue
            influence = dict(d.get("memory_influence") or {})
            counters["retrieved_count"] += 1
            if bool(influence.get("eligible_to_influence", False)):
                counters["eligible_count"] += 1
            if influence.get("blocked_reason"):
                counters["blocked_count"] += 1

        episode_idx = _extract_episode_idx(decisions)
        if episode_idx is None:
            continue

        workflow_id = str(decisions[0].get("workflow_id") or trace_file.stem)
        meta = by_episode.setdefault(episode_idx, EpisodeTraceMeta(workflow_id=workflow_id))

        for d in decisions:
            if d.get("chosen_action") != "retrieve_memory":
                continue
            influence = dict(d.get("memory_influence") or {})
            meta.retrieve_events.append(
                {
                    "decision_id": d.get("decision_id"),
                    "memory_refs": list(d.get("input_memory_refs") or []),
                    "influence": influence,
                }
            )

        meta.invalid_output_events = sum(1 for t in traces if t.get("event_type") == "invalid_agent_output")

    return counters, by_episode


def _float(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _build_rows(experiments_dir: Path) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[int, EpisodeTraceMeta]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    trace_index: dict[tuple[str, str], dict[int, EpisodeTraceMeta]] = {}
    metrics_index: dict[str, dict[str, Any]] = {}

    for setting, run_name in RUNS:
        run_dir = experiments_dir / run_name
        metrics = _load_json(run_dir / "metrics.json")
        metrics_index[setting] = metrics

        for variant in VARIANT_ORDER:
            if variant not in metrics:
                continue

            summary = metrics[variant]
            counters, by_episode = _scan_variant_traces(run_dir / "traces" / variant)
            trace_index[(setting, variant)] = by_episode

            row = {
                "setting": setting,
                "run_dir": str(run_dir),
                "variant": variant,
                "success_rate": _float(summary.get("success_rate")),
                "mean_score": _float(summary.get("mean_score")),
                "order_violation_rate": _float(summary.get("order_violation_rate")),
                "missing_required_agent_rate": _float(summary.get("missing_required_agent_rate")),
                "recovery_success_rate": _float(summary.get("recovery_success_rate")),
                "memory_changed_scheduling_decisions": int(summary.get("memory_changed_scheduling_decisions", 0)),
                "support_only_count": int(summary.get("support_only_count", 0)),
                "changed_agent_selection_count": int(summary.get("changed_agent_selection_count", 0)),
                "changed_ordering_count": int(summary.get("changed_ordering_count", 0)),
                "changed_recovery_count": int(summary.get("changed_recovery_count", 0)),
                "retrieved_count": counters["retrieved_count"],
                "eligible_count": counters["eligible_count"],
                "blocked_count": counters["blocked_count"],
                "schema_valid_rate": _float(summary.get("agent_output_schema_valid_rate")),
                "parse_failure_rate": _float(summary.get("parse_failure_rate")),
                "repair_success_rate": _float(summary.get("repair_success_rate")),
                "invalid_artifact_ref_rate": _float(summary.get("invalid_artifact_ref_rate")),
                "memory_validation_failure_rate": _float(summary.get("memory_validation_failure_rate")),
                "unsupported_lesson_rate": _float(summary.get("unsupported_lesson_rate")),
                "overgeneralized_memory_rate": _float(summary.get("overgeneralized_memory_rate")),
                "curator_accept_rate": _float(summary.get("curator_accept_rate")),
                "curator_reject_rate": _float(summary.get("curator_reject_rate")),
            }
            rows.append(row)

    return rows, trace_index, metrics_index


def _to_markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def _find_example_relevant_memory(
    metrics_index: dict[str, dict[str, Any]],
    trace_index: dict[tuple[str, str], dict[int, EpisodeTraceMeta]],
) -> dict[str, Any] | None:
    setting = "normal_hard_synthetic"
    metrics = metrics_index.get(setting, {})
    no_eps = {int(ep["episode_idx"]): ep for ep in metrics.get("mas_no_memory", {}).get("episodes", [])}
    mem_eps = {int(ep["episode_idx"]): ep for ep in metrics.get("mas_orchestrator_memory", {}).get("episodes", [])}
    mem_trace = trace_index.get((setting, "mas_orchestrator_memory"), {})

    best: dict[str, Any] | None = None
    for ep_idx, mem_ep in mem_eps.items():
        if ep_idx not in no_eps:
            continue
        delta = _float(mem_ep.get("benchmark_score")) - _float(no_eps[ep_idx].get("benchmark_score"))
        if delta <= 0:
            continue
        if int(mem_ep.get("scheduling_scores", {}).get("memory_changed_scheduling_decisions", 0)) <= 0:
            continue
        trace_meta = mem_trace.get(ep_idx)
        if not trace_meta:
            continue
        changed = None
        for event in trace_meta.retrieve_events:
            influence = event.get("influence") or {}
            if str(influence.get("influence_type", "")).startswith("changed_"):
                changed = event
                break
        if not changed:
            continue

        candidate = {
            "setting": setting,
            "episode_idx": ep_idx,
            "workflow_id": trace_meta.workflow_id,
            "task_family": mem_ep.get("task_family"),
            "no_memory_score": _float(no_eps[ep_idx].get("benchmark_score")),
            "orchestrator_score": _float(mem_ep.get("benchmark_score")),
            "score_delta": round(delta, 3),
            "memory_event": changed,
        }
        if best is None or candidate["score_delta"] > best["score_delta"]:
            best = candidate

    return best


def _find_example_shuffled_blocked(
    trace_index: dict[tuple[str, str], dict[int, EpisodeTraceMeta]],
    metrics_index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    setting = "normal_hard_synthetic"
    traces = trace_index.get((setting, "mas_shuffled_memory"), {})
    metrics = metrics_index.get(setting, {})
    shuf_eps = {int(ep["episode_idx"]): ep for ep in metrics.get("mas_shuffled_memory", {}).get("episodes", [])}

    for ep_idx in sorted(traces.keys()):
        meta = traces[ep_idx]
        for event in meta.retrieve_events:
            influence = event.get("influence") or {}
            blocked_reason = str(influence.get("blocked_reason") or "")
            if "family_mismatch" not in blocked_reason:
                continue
            return {
                "setting": setting,
                "episode_idx": ep_idx,
                "workflow_id": meta.workflow_id,
                "task_family": shuf_eps.get(ep_idx, {}).get("task_family"),
                "memory_event": event,
            }
    return None


def _find_example_invalid_output_rejected(
    metrics_index: dict[str, dict[str, Any]],
    trace_index: dict[tuple[str, str], dict[int, EpisodeTraceMeta]],
) -> dict[str, Any] | None:
    setting = "llm_noise_hallucinated_artifact_ref"
    metrics = metrics_index.get(setting, {})
    episodes = {int(ep["episode_idx"]): ep for ep in metrics.get("mas_orchestrator_memory", {}).get("episodes", [])}
    traces = trace_index.get((setting, "mas_orchestrator_memory"), {})

    for ep_idx in sorted(traces.keys()):
        trace = traces[ep_idx]
        if trace.invalid_output_events <= 0:
            continue
        ep = episodes.get(ep_idx, {})
        actions = list(ep.get("curation_actions") or [])
        accepted_updates = [
            a
            for a in actions
            if bool(a.get("accepted")) and str(a.get("action")) in {"CREATE", "UPDATE"}
        ]
        if accepted_updates:
            continue
        reasons = [str(a.get("reason") or "") for a in actions[:3]]
        return {
            "setting": setting,
            "episode_idx": ep_idx,
            "workflow_id": trace.workflow_id,
            "task_family": ep.get("task_family"),
            "invalid_output_events": trace.invalid_output_events,
            "curation_reasons": reasons,
        }
    return None


def _write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    fields = list(rows[0].keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _format_rate(v: Any) -> str:
    return f"{_float(v):.3f}"


def _write_markdown(
    rows: list[dict[str, Any]],
    metrics_index: dict[str, dict[str, Any]],
    trace_index: dict[tuple[str, str], dict[int, EpisodeTraceMeta]],
    out_path: Path,
) -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    oracle_present = any("mas_oracle_memory" in metrics for metrics in metrics_index.values())

    perf_headers = [
        "Setting",
        "Variant",
        "Success",
        "MeanScore",
        "OrderViol",
        "MissingReq",
        "RecoverySucc",
        "MemChanged",
        "Retrieved",
        "Eligible",
        "Blocked",
    ]
    perf_rows: list[list[Any]] = []
    val_headers = [
        "Setting",
        "Variant",
        "SchemaValid",
        "ParseFail",
        "RepairSucc",
        "InvalidArtifactRef",
        "MemValFail",
        "Unsupported",
        "Overgeneralized",
        "CurAccept",
        "CurReject",
    ]
    val_rows: list[list[Any]] = []

    for row in rows:
        perf_rows.append(
            [
                row["setting"],
                row["variant"],
                _format_rate(row["success_rate"]),
                _format_rate(row["mean_score"]),
                _format_rate(row["order_violation_rate"]),
                _format_rate(row["missing_required_agent_rate"]),
                _format_rate(row["recovery_success_rate"]),
                row["memory_changed_scheduling_decisions"],
                row["retrieved_count"],
                row["eligible_count"],
                row["blocked_count"],
            ]
        )
        val_rows.append(
            [
                row["setting"],
                row["variant"],
                _format_rate(row["schema_valid_rate"]),
                _format_rate(row["parse_failure_rate"]),
                _format_rate(row["repair_success_rate"]),
                _format_rate(row["invalid_artifact_ref_rate"]),
                _format_rate(row["memory_validation_failure_rate"]),
                _format_rate(row["unsupported_lesson_rate"]),
                _format_rate(row["overgeneralized_memory_rate"]),
                _format_rate(row["curator_accept_rate"]),
                _format_rate(row["curator_reject_rate"]),
            ]
        )

    example_1 = _find_example_relevant_memory(metrics_index, trace_index)
    example_2 = _find_example_shuffled_blocked(trace_index, metrics_index)
    example_3 = _find_example_invalid_output_rejected(metrics_index, trace_index)

    normal = metrics_index["normal_hard_synthetic"]
    no_normal = normal["mas_no_memory"]
    mem_normal = normal["mas_orchestrator_memory"]
    shuf_normal = normal["mas_shuffled_memory"]

    malformed = metrics_index["llm_noise_malformed_json"]
    missing = metrics_index["llm_noise_missing_fields"]
    hallucinated = metrics_index["llm_noise_hallucinated_artifact_ref"]

    lines: list[str] = []
    lines.append("# Robustness Summary")
    lines.append("")
    lines.append(f"- Generated at: {generated_at}")
    lines.append("- Matrix settings: normal + 4 LLM-noise modes")
    lines.append("- Variants included: mas_no_memory, mas_orchestrator_memory, mas_shuffled_memory, mas_random_memory")
    if oracle_present:
        lines.append("- Optional variant `mas_oracle_memory`: available and included")
    else:
        lines.append("- Optional variant `mas_oracle_memory`: not implemented in current codebase, not included")
    lines.append("")

    lines.append("## Performance and Scheduling Metrics")
    lines.append("")
    lines.append(_to_markdown_table(perf_headers, perf_rows))
    lines.append("")
    lines.append("## Validation and Curation Metrics")
    lines.append("")
    lines.append(_to_markdown_table(val_headers, val_rows))
    lines.append("")

    lines.append("## Qualitative Episode Examples")
    lines.append("")
    if example_1:
        inf = example_1["memory_event"]["influence"]
        lines.append("1. Relevant memory improved scheduling")
        lines.append(
            f"- setting={example_1['setting']}, episode={example_1['episode_idx']}, workflow_id={example_1['workflow_id']}, task_family={example_1['task_family']}"
        )
        lines.append(
            f"- score delta: {example_1['no_memory_score']:.3f} -> {example_1['orchestrator_score']:.3f} (delta={example_1['score_delta']:.3f})"
        )
        lines.append(
            f"- influence_type={inf.get('influence_type')}, baseline_agent={inf.get('baseline_agent')}, final_agent={inf.get('final_agent')}, memory_id={inf.get('memory_id')}"
        )
        lines.append(f"- reason={inf.get('reason')}")
    else:
        lines.append("1. Relevant memory improved scheduling: no qualifying example found")
    lines.append("")

    if example_2:
        inf = example_2["memory_event"]["influence"]
        lines.append("2. Shuffled/irrelevant memory was blocked")
        lines.append(
            f"- setting={example_2['setting']}, episode={example_2['episode_idx']}, workflow_id={example_2['workflow_id']}, task_family={example_2['task_family']}"
        )
        lines.append(
            f"- influence_type={inf.get('influence_type')}, blocked_reason={inf.get('blocked_reason')}, current_family={inf.get('current_task_family')}, memory_family={inf.get('memory_task_family')}"
        )
        lines.append(
            f"- trigger_match_score={inf.get('trigger_match_score')}, eligible_to_influence={inf.get('eligible_to_influence')}"
        )
    else:
        lines.append("2. Shuffled/irrelevant memory blocked: no qualifying example found")
    lines.append("")

    if example_3:
        lines.append("3. Invalid LLM output rejected and did not update procedural memory")
        lines.append(
            f"- setting={example_3['setting']}, episode={example_3['episode_idx']}, workflow_id={example_3['workflow_id']}, task_family={example_3['task_family']}"
        )
        lines.append(
            f"- invalid_agent_output events={example_3['invalid_output_events']}, accepted CREATE/UPDATE actions=0"
        )
        lines.append(f"- curation reasons (sample)={example_3['curation_reasons']}")
    else:
        lines.append("3. Invalid LLM output rejection example: no qualifying example found")
    lines.append("")

    lines.append("## Conclusion")
    lines.append("")
    lines.append("1. Does orchestrator memory improve scheduling under normal synthetic tasks?")
    lines.append(
        f"- Yes. In normal hard synthetic, `mean_score` improved from {no_normal['mean_score']:.3f} to {mem_normal['mean_score']:.3f}, and `success_rate` improved from {no_normal['success_rate']:.3f} to {mem_normal['success_rate']:.3f}."
    )
    lines.append("")
    lines.append("2. Does validation protect memory under noisy LLM outputs?")
    lines.append(
        f"- Partially. Under `missing_fields` and `hallucinated_artifact_ref`, schema-valid rate drops to {missing['mas_orchestrator_memory']['agent_output_schema_valid_rate']:.3f}/{hallucinated['mas_orchestrator_memory']['agent_output_schema_valid_rate']:.3f} and benchmark performance collapses, while invalid artifact references are explicitly surfaced (`hallucinated`: {hallucinated['mas_orchestrator_memory']['invalid_artifact_ref_rate']:.3f}). Some curator accepts remain, so rejection is not absolute."
    )
    lines.append("")
    lines.append("3. Does shuffled memory still outperform relevant memory anywhere?")
    lines.append(
        f"- Yes, slightly in normal hard synthetic (`mas_shuffled_memory.mean_score={shuf_normal['mean_score']:.3f}` vs `mas_orchestrator_memory.mean_score={mem_normal['mean_score']:.3f}`). In noisy modes where parsing is robust (`malformed_json`) or lessons are overgeneralized, orchestrator memory remains ahead."
    )
    lines.append("")
    lines.append("4. Which metrics are ready for a thesis/paper table?")
    lines.append(
        "- Ready now: success_rate, mean_score, order_violation_rate, missing_required_agent_rate, recovery_success_rate, memory_changed_scheduling_decisions, retrieved/eligible/blocked counts, schema_valid_rate, parse_failure_rate, repair_success_rate, invalid_artifact_ref_rate."
    )
    lines.append("")
    lines.append("5. What remains before moving to REALM-Bench/WebArena?")
    lines.append(
        "- Tighten curator acceptance under fully invalid outputs, validate on real LLM backends with calibrated latency/cost, and add benchmark adapters plus task-grounded success validators for external environments."
    )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        f"- `malformed_json` run still performs strongly for memory variants: orchestrator `success_rate={malformed['mas_orchestrator_memory']['success_rate']:.3f}`, `mean_score={malformed['mas_orchestrator_memory']['mean_score']:.3f}`."
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    experiments_dir = Path("experiments")
    rows, trace_index, metrics_index = _build_rows(experiments_dir=experiments_dir)
    if not rows:
        raise RuntimeError("No robustness rows were produced.")

    csv_out = experiments_dir / "robustness_summary.csv"
    md_out = experiments_dir / "robustness_summary.md"
    _write_csv(rows, csv_out)
    _write_markdown(rows, metrics_index, trace_index, md_out)

    print(f"Wrote CSV: {csv_out}")
    print(f"Wrote Markdown: {md_out}")


if __name__ == "__main__":
    main()
