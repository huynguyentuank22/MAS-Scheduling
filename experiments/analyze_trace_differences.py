#!/usr/bin/env python
"""Compare trace decisions between mas_no_memory and mas_orchestrator_memory.

Outputs:
- CSV per-episode comparison with decision and metric deltas
- Markdown summary with aggregate findings
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EPISODE_PATTERN = re.compile(r"\(episode\s+(\d+)\)", re.IGNORECASE)
AGENT_FROM_RATIONALE_PATTERN = re.compile(r"(?:→|->)\s*([A-Za-z_][A-Za-z0-9_-]*)\s*$")
CALL_ACTIONS = {"call_agent", "call_recovery_agent", "spawn_agent"}


@dataclass
class EpisodeTrace:
    episode_idx: int
    workflow_id: str
    trace_file: Path
    decision_actions: list[str]
    decision_tokens_full: list[str]
    decision_tokens_effective: list[str]
    agent_sequence: list[str]
    retrieve_memory_events: int
    selected_memories: list[str]
    memory_refs: list[str]
    support_only_count: int
    changed_agent_selection_count: int
    changed_ordering_count: int
    changed_recovery_count: int
    agent_call_count: int
    retry_count: int
    replan_count: int
    total_cost: float
    avg_cost: float
    total_latency_sec: float
    avg_latency_sec: float


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _extract_episode_idx(decision_events: list[dict[str, Any]]) -> int | None:
    for event in decision_events:
        rationale = event.get("rationale_summary") or ""
        match = EPISODE_PATTERN.search(rationale)
        if match:
            return int(match.group(1)) - 1
    return None


def _extract_agent_from_rationale(rationale: str) -> str | None:
    match = AGENT_FROM_RATIONALE_PATTERN.search(rationale or "")
    if not match:
        return None
    return match.group(1)


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _tokenize_decisions(
    decision_events: list[dict[str, Any]],
    agent_sequence: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Return (actions, full_tokens, effective_tokens)."""
    actions: list[str] = []
    full_tokens: list[str] = []
    effective_tokens: list[str] = []

    call_idx = 0
    for event in decision_events:
        action = str(event.get("chosen_action") or "")
        if not action:
            continue

        token = action
        if action in CALL_ACTIONS:
            rationale = str(event.get("rationale_summary") or "")
            agent = _extract_agent_from_rationale(rationale)
            if not agent and call_idx < len(agent_sequence):
                agent = agent_sequence[call_idx]
            call_idx += 1
            token = f"{action}:{agent or 'unknown'}"
        elif action == "retrieve_memory":
            refs = event.get("input_memory_refs") or []
            token = f"retrieve_memory:{len(refs)}"

        actions.append(action)
        full_tokens.append(token)
        if action != "retrieve_memory":
            effective_tokens.append(token)

    return actions, full_tokens, effective_tokens


def _float_or_zero(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _load_variant_traces(variant_dir: Path) -> dict[int, EpisodeTrace]:
    episode_map: dict[int, EpisodeTrace] = {}

    for trace_file in sorted(variant_dir.glob("*.jsonl")):
        records = _load_jsonl(trace_file)
        decision_events = [r for r in records if r.get("_type") == "DecisionEvent"]
        execution_events = [r for r in records if r.get("_type") == "ExecutionTraceEvent"]

        episode_idx = _extract_episode_idx(decision_events)
        if episode_idx is None:
            raise ValueError(f"Could not determine episode index from trace: {trace_file}")

        workflow_id = str(decision_events[0].get("workflow_id") or trace_file.stem)

        agent_sequence = [
            str(ev.get("actor"))
            for ev in execution_events
            if ev.get("event_type") == "agent_call" and ev.get("actor")
        ]

        retrieve_events = [d for d in decision_events if d.get("chosen_action") == "retrieve_memory"]
        support_only_count = 0
        changed_agent_selection_count = 0
        changed_ordering_count = 0
        changed_recovery_count = 0
        for d in retrieve_events:
            influence_type = str((d.get("memory_influence") or {}).get("influence_type") or "none")
            if influence_type == "support_only":
                support_only_count += 1
            elif influence_type == "changed_agent_selection":
                changed_agent_selection_count += 1
            elif influence_type == "changed_ordering":
                changed_ordering_count += 1
            elif influence_type == "changed_recovery":
                changed_recovery_count += 1

        selected_memories = _unique_preserve_order(
            [
                str(ref)
                for d in retrieve_events
                for ref in (d.get("input_memory_refs") or [])
                if ref
            ]
        )
        memory_refs = _unique_preserve_order(
            [
                str(ref)
                for d in decision_events
                for ref in (d.get("input_memory_refs") or [])
                if ref
            ]
        )

        actions, tokens_full, tokens_effective = _tokenize_decisions(decision_events, agent_sequence)

        call_decisions = [d for d in decision_events if d.get("chosen_action") in CALL_ACTIONS]
        total_cost = sum(_float_or_zero(d.get("cost")) for d in call_decisions)
        total_latency = sum(_float_or_zero(d.get("latency_sec")) for d in call_decisions)
        call_count = len(call_decisions)

        episode_map[episode_idx] = EpisodeTrace(
            episode_idx=episode_idx,
            workflow_id=workflow_id,
            trace_file=trace_file,
            decision_actions=actions,
            decision_tokens_full=tokens_full,
            decision_tokens_effective=tokens_effective,
            agent_sequence=agent_sequence,
            retrieve_memory_events=len(retrieve_events),
            selected_memories=selected_memories,
            memory_refs=memory_refs,
            support_only_count=support_only_count,
            changed_agent_selection_count=changed_agent_selection_count,
            changed_ordering_count=changed_ordering_count,
            changed_recovery_count=changed_recovery_count,
            agent_call_count=call_count,
            retry_count=sum(1 for a in actions if a == "retry"),
            replan_count=sum(1 for a in actions if a == "replan"),
            total_cost=round(total_cost, 6),
            avg_cost=round(total_cost / call_count, 6) if call_count else 0.0,
            total_latency_sec=round(total_latency, 6),
            avg_latency_sec=round(total_latency / call_count, 6) if call_count else 0.0,
        )

    return episode_map


def _diff_tokens(left: list[str], right: list[str], limit: int = 8) -> tuple[int, str]:
    mismatches: list[str] = []
    max_len = max(len(left), len(right))

    for i in range(max_len):
        lval = left[i] if i < len(left) else "<none>"
        rval = right[i] if i < len(right) else "<none>"
        if lval != rval:
            mismatches.append(f"{i}:{lval} != {rval}")

    summary = "; ".join(mismatches[:limit])
    if len(mismatches) > limit:
        summary += "; ..."
    return len(mismatches), summary


def _join_list(items: list[str]) -> str:
    return "|".join(items)


def _build_metrics_index(metrics: dict[str, Any], variant: str) -> dict[int, dict[str, Any]]:
    episodes = metrics.get(variant, {}).get("episodes", [])
    return {int(ep["episode_idx"]): ep for ep in episodes}


def _write_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    if not rows:
        raise ValueError("No rows generated for CSV")

    fields = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_summary_markdown(
    rows: list[dict[str, Any]],
    markdown_path: Path,
    base_dir: Path,
    csv_path: Path,
) -> None:
    total = len(rows)
    with_memory_retrieval = sum(1 for r in rows if int(r["mem_retrieve_memory_events"]) > 0)
    changed_sched = sum(1 for r in rows if str(r["memory_changed_scheduling_decisions"]) == "True")
    only_retrieve_diff = sum(
        1
        for r in rows
        if int(r["decision_diff_full_count"]) > 0 and int(r["decision_diff_effective_count"]) == 0
    )

    def _sum_float(key: str) -> float:
        return round(sum(float(r[key]) for r in rows), 6)

    def _sum_int(key: str) -> int:
        return int(sum(int(r[key]) for r in rows))

    lines: list[str] = []
    lines.append("# Trace Difference Analysis")
    lines.append("")
    lines.append(f"- Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Base directory: `{base_dir}`")
    lines.append(f"- Episode rows: {total}")
    lines.append(f"- CSV: `{csv_path}`")
    lines.append("")

    lines.append("## Key Findings")
    lines.append("")
    lines.append(f"- Episodes with retrieve_memory events: {with_memory_retrieval}/{total}")
    lines.append(f"- Episodes where scheduling decisions changed: {changed_sched}/{total}")
    lines.append(f"- Episodes where differences are retrieve_memory-only instrumentation: {only_retrieve_diff}/{total}")
    lines.append(f"- support_only_count (retrieve events): {_sum_int('mem_support_only_count')}")
    lines.append(f"- changed_agent_selection_count (retrieve events): {_sum_int('mem_changed_agent_selection_count')}")
    lines.append(f"- changed_ordering_count (retrieve events): {_sum_int('mem_changed_ordering_count')}")
    lines.append(f"- changed_recovery_count (retrieve events): {_sum_int('mem_changed_recovery_count')}")
    lines.append("")

    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append("| Metric | mas_no_memory | mas_orchestrator_memory | Delta (mem - no_mem) |")
    lines.append("|---|---:|---:|---:|")

    metric_keys = [
        ("agent_call_count", "Agent call count"),
        ("retry_count", "Retry count"),
        ("replan_count", "Replan count"),
        ("total_cost", "Total cost"),
        ("total_latency_sec", "Total latency sec"),
    ]

    for key, label in metric_keys:
        no_key = f"no_{key}"
        mem_key = f"mem_{key}"
        if key in {"total_cost", "total_latency_sec"}:
            no_val = _sum_float(no_key)
            mem_val = _sum_float(mem_key)
            delta = round(mem_val - no_val, 6)
        else:
            no_val = _sum_int(no_key)
            mem_val = _sum_int(mem_key)
            delta = mem_val - no_val
        lines.append(f"| {label} | {no_val} | {mem_val} | {delta} |")

    lines.append("")
    lines.append("## Episodes With Scheduling Changes")
    lines.append("")
    changed_rows = [r for r in rows if str(r["memory_changed_scheduling_decisions"]) == "True"]
    if not changed_rows:
        lines.append("- None")
    else:
        for row in changed_rows[:15]:
            lines.append(
                "- "
                f"episode_idx={row['episode_idx']}, "
                f"task_family={row['task_family']}, "
                f"no_agents={row['no_agent_sequence']}, "
                f"mem_agents={row['mem_agent_sequence']}, "
                f"diff={row['decision_diff_effective_summary']}"
            )

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_analysis(base_dir: Path, csv_path: Path, markdown_path: Path) -> None:
    metrics_path = base_dir / "metrics.json"
    traces_root = base_dir / "traces"

    metrics = _load_json(metrics_path)
    no_metrics_idx = _build_metrics_index(metrics, "mas_no_memory")
    mem_metrics_idx = _build_metrics_index(metrics, "mas_orchestrator_memory")

    no_traces = _load_variant_traces(traces_root / "mas_no_memory")
    mem_traces = _load_variant_traces(traces_root / "mas_orchestrator_memory")

    episode_indices = sorted(set(no_traces.keys()) | set(mem_traces.keys()))
    rows: list[dict[str, Any]] = []

    for episode_idx in episode_indices:
        no_ep = no_traces.get(episode_idx)
        mem_ep = mem_traces.get(episode_idx)

        if no_ep is None or mem_ep is None:
            raise ValueError(f"Missing trace in one variant for episode {episode_idx}")

        full_diff_count, full_diff_summary = _diff_tokens(
            no_ep.decision_tokens_full,
            mem_ep.decision_tokens_full,
        )
        eff_diff_count, eff_diff_summary = _diff_tokens(
            no_ep.decision_tokens_effective,
            mem_ep.decision_tokens_effective,
        )

        memory_changed_sched = eff_diff_count > 0

        task_family = (
            no_metrics_idx.get(episode_idx, {}).get("task_family")
            or mem_metrics_idx.get(episode_idx, {}).get("task_family")
            or "unknown"
        )

        row = {
            "episode_idx": episode_idx,
            "task_family": task_family,
            "no_workflow_id": no_ep.workflow_id,
            "mem_workflow_id": mem_ep.workflow_id,
            "no_trace_file": str(no_ep.trace_file),
            "mem_trace_file": str(mem_ep.trace_file),
            "no_agent_sequence": _join_list(no_ep.agent_sequence),
            "mem_agent_sequence": _join_list(mem_ep.agent_sequence),
            "no_retrieve_memory_events": no_ep.retrieve_memory_events,
            "mem_retrieve_memory_events": mem_ep.retrieve_memory_events,
            "no_selected_memories": _join_list(no_ep.selected_memories),
            "mem_selected_memories": _join_list(mem_ep.selected_memories),
            "no_memory_refs": _join_list(no_ep.memory_refs),
            "mem_memory_refs": _join_list(mem_ep.memory_refs),
            "no_support_only_count": no_ep.support_only_count,
            "mem_support_only_count": mem_ep.support_only_count,
            "no_changed_agent_selection_count": no_ep.changed_agent_selection_count,
            "mem_changed_agent_selection_count": mem_ep.changed_agent_selection_count,
            "no_changed_ordering_count": no_ep.changed_ordering_count,
            "mem_changed_ordering_count": mem_ep.changed_ordering_count,
            "no_changed_recovery_count": no_ep.changed_recovery_count,
            "mem_changed_recovery_count": mem_ep.changed_recovery_count,
            "no_decisions_full": _join_list(no_ep.decision_tokens_full),
            "mem_decisions_full": _join_list(mem_ep.decision_tokens_full),
            "no_decisions_effective": _join_list(no_ep.decision_tokens_effective),
            "mem_decisions_effective": _join_list(mem_ep.decision_tokens_effective),
            "decision_diff_full_count": full_diff_count,
            "decision_diff_full_summary": full_diff_summary,
            "decision_diff_effective_count": eff_diff_count,
            "decision_diff_effective_summary": eff_diff_summary,
            "memory_changed_scheduling_decisions": memory_changed_sched,
            "no_agent_call_count": no_ep.agent_call_count,
            "mem_agent_call_count": mem_ep.agent_call_count,
            "no_retry_count": no_ep.retry_count,
            "mem_retry_count": mem_ep.retry_count,
            "no_replan_count": no_ep.replan_count,
            "mem_replan_count": mem_ep.replan_count,
            "no_total_cost": no_ep.total_cost,
            "mem_total_cost": mem_ep.total_cost,
            "no_avg_cost": no_ep.avg_cost,
            "mem_avg_cost": mem_ep.avg_cost,
            "no_total_latency_sec": no_ep.total_latency_sec,
            "mem_total_latency_sec": mem_ep.total_latency_sec,
            "no_avg_latency_sec": no_ep.avg_latency_sec,
            "mem_avg_latency_sec": mem_ep.avg_latency_sec,
        }
        rows.append(row)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(rows, csv_path)
    _write_summary_markdown(rows, markdown_path, base_dir, csv_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare trace differences between two OLM-MAS variants")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("experiments/stabilization_sprint_20260508"),
        help="Directory containing metrics.json and traces/<variant>",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=Path("experiments/stabilization_sprint_20260508/trace_differences.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path("experiments/stabilization_sprint_20260508/trace_differences_summary.md"),
        help="Output markdown summary path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_analysis(
        base_dir=args.base_dir,
        csv_path=args.csv_out,
        markdown_path=args.summary_out,
    )
    print(f"CSV written: {args.csv_out}")
    print(f"Summary written: {args.summary_out}")


if __name__ == "__main__":
    main()
