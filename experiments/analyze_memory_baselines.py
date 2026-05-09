#!/usr/bin/env python
"""Analyze synthetic memory baselines for latest run.

Reads metrics/traces/memories and explains why shuffled memory may outperform
orchestrator memory on current synthetic setup.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EPISODE_PATTERN = re.compile(r"\(episode\s+(\d+)\)", re.IGNORECASE)


@dataclass
class MemoryMeta:
    variant: str
    memory_id: str
    trigger_task_family: str
    source_family: str
    confidence: float
    recommended_schedule: list[str] = field(default_factory=list)


@dataclass
class EpisodeInfo:
    episode_idx: int
    task_family: str
    score: float
    success: bool
    scheduling_scores: dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodeTraceStats:
    retrieve_events: int = 0
    influence_counts: Counter = field(default_factory=Counter)
    memory_counter: Counter = field(default_factory=Counter)
    trigger_counter: Counter = field(default_factory=Counter)
    source_counter: Counter = field(default_factory=Counter)
    eligible_count: int = 0
    blocked_count: int = 0
    blocked_by_family_mismatch_count: int = 0
    applied_changed_count: int = 0
    support_only_count: int = 0
    trigger_match_scores: list[float] = field(default_factory=list)


@dataclass
class RetrieveRecord:
    variant: str
    workflow_id: str
    episode_idx: int
    task_family: str
    memory_id: str
    trigger_task_family: str
    source_family: str
    influence_type: str
    confidence: float
    trigger_match_score: float
    eligible_to_influence: bool
    blocked_reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze memory baseline behavior from synthetic run outputs")
    parser.add_argument(
        "--experiments-dir",
        type=Path,
        default=Path("experiments"),
        help="Root experiments directory",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Specific run directory (contains metrics.json/traces/memories). If omitted, latest is used.",
    )
    parser.add_argument("--top-n", type=int, default=8, help="Top examples to include")
    parser.add_argument("--csv-out", type=Path, default=None, help="Output CSV path")
    parser.add_argument("--md-out", type=Path, default=None, help="Output markdown path")
    return parser.parse_args()


def detect_latest_run(experiments_dir: Path) -> Path:
    candidates: list[tuple[float, Path]] = []

    if (experiments_dir / "metrics.json").exists() and (experiments_dir / "traces").is_dir():
        candidates.append(((experiments_dir / "metrics.json").stat().st_mtime, experiments_dir))

    for child in experiments_dir.iterdir():
        if not child.is_dir():
            continue
        metrics_path = child / "metrics.json"
        traces_path = child / "traces"
        if metrics_path.exists() and traces_path.is_dir():
            candidates.append((metrics_path.stat().st_mtime, child))

    if not candidates:
        raise FileNotFoundError(f"No run directory with metrics/traces found under {experiments_dir}")

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_episode_lookup(metrics: dict[str, Any]) -> dict[str, dict[int, EpisodeInfo]]:
    lookup: dict[str, dict[int, EpisodeInfo]] = {}

    for variant, data in metrics.items():
        by_idx: dict[int, EpisodeInfo] = {}
        for ep in data.get("episodes", []):
            idx = int(ep.get("episode_idx", -1))
            if idx < 0:
                continue
            by_idx[idx] = EpisodeInfo(
                episode_idx=idx,
                task_family=str(ep.get("task_family") or "unknown"),
                score=float(ep.get("benchmark_score", 0.0)),
                success=bool(ep.get("benchmark_success", False)),
                scheduling_scores=dict(ep.get("scheduling_scores") or {}),
            )
        lookup[variant] = by_idx

    return lookup


def load_memory_catalog(run_dir: Path) -> dict[str, dict[str, MemoryMeta]]:
    catalog: dict[str, dict[str, MemoryMeta]] = defaultdict(dict)
    memories_root = run_dir / "memories"
    if not memories_root.exists():
        return catalog

    for variant_dir in memories_root.iterdir():
        if not variant_dir.is_dir():
            continue
        variant = variant_dir.name
        for mem_file in variant_dir.glob("*.json"):
            data = load_json(mem_file)
            trigger = dict(data.get("trigger") or {})
            mem_id = str(data.get("memory_id") or mem_file.stem)
            catalog[variant][mem_id] = MemoryMeta(
                variant=variant,
                memory_id=mem_id,
                trigger_task_family=str(trigger.get("task_family") or "unknown"),
                source_family=str(trigger.get("source_family") or ""),
                confidence=float(data.get("confidence", 0.0)),
                recommended_schedule=list(data.get("recommended_schedule") or []),
            )

    return catalog


def extract_episode_idx(decisions: list[dict[str, Any]]) -> int | None:
    for d in decisions:
        rationale = str(d.get("rationale_summary") or "")
        match = EPISODE_PATTERN.search(rationale)
        if match:
            return int(match.group(1)) - 1
    return None


def scan_traces(
    run_dir: Path,
    episode_lookup: dict[str, dict[int, EpisodeInfo]],
    memory_catalog: dict[str, dict[str, MemoryMeta]],
) -> tuple[list[RetrieveRecord], dict[tuple[str, int], EpisodeTraceStats]]:
    retrieve_records: list[RetrieveRecord] = []
    episode_stats: dict[tuple[str, int], EpisodeTraceStats] = {}

    traces_root = run_dir / "traces"
    for variant_dir in traces_root.iterdir():
        if not variant_dir.is_dir():
            continue

        variant = variant_dir.name
        variant_eps = episode_lookup.get(variant, {})
        mem_map = memory_catalog.get(variant, {})

        for trace_file in variant_dir.glob("*.jsonl"):
            records = load_jsonl(trace_file)
            decisions = [r for r in records if r.get("_type") == "DecisionEvent"]
            if not decisions:
                continue

            ep_idx = extract_episode_idx(decisions)
            if ep_idx is None:
                continue

            ep_info = variant_eps.get(ep_idx)
            if ep_info is None:
                continue

            key = (variant, ep_idx)
            stats = episode_stats.setdefault(key, EpisodeTraceStats())
            workflow_id = str(decisions[0].get("workflow_id") or trace_file.stem)

            for d in decisions:
                if d.get("chosen_action") != "retrieve_memory":
                    continue

                stats.retrieve_events += 1
                influence = dict(d.get("memory_influence") or {})
                influence_type = str(influence.get("influence_type") or "none")
                stats.influence_counts[influence_type] += 1
                trigger_match_score = float(influence.get("trigger_match_score") or 0.0)
                eligible_to_influence = bool(influence.get("eligible_to_influence", False))
                blocked_reason = str(influence.get("blocked_reason") or "")
                stats.trigger_match_scores.append(trigger_match_score)
                if eligible_to_influence:
                    stats.eligible_count += 1
                if blocked_reason:
                    stats.blocked_count += 1
                    if "family_mismatch" in blocked_reason:
                        stats.blocked_by_family_mismatch_count += 1
                if influence_type in {"changed_agent_selection", "changed_ordering", "changed_recovery"}:
                    stats.applied_changed_count += 1
                if influence_type == "support_only":
                    stats.support_only_count += 1

                refs = list(d.get("input_memory_refs") or [])
                if not refs and influence.get("memory_id"):
                    refs = [str(influence.get("memory_id"))]

                for mem_id in refs:
                    mem_id = str(mem_id)
                    mem = mem_map.get(mem_id)
                    trigger_family = mem.trigger_task_family if mem else "unknown"
                    source_family = mem.source_family if mem else ""
                    confidence = mem.confidence if mem else 0.0

                    stats.memory_counter[mem_id] += 1
                    stats.trigger_counter[trigger_family] += 1
                    if source_family:
                        stats.source_counter[source_family] += 1

                    retrieve_records.append(
                        RetrieveRecord(
                            variant=variant,
                            workflow_id=workflow_id,
                            episode_idx=ep_idx,
                            task_family=ep_info.task_family,
                            memory_id=mem_id,
                            trigger_task_family=trigger_family,
                            source_family=source_family,
                            influence_type=influence_type,
                            confidence=confidence,
                            trigger_match_score=trigger_match_score,
                            eligible_to_influence=eligible_to_influence,
                            blocked_reason=blocked_reason,
                        )
                    )

    return retrieve_records, episode_stats


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if q <= 0:
        return float(min(values))
    if q >= 1:
        return float(max(values))
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    low = int(idx)
    high = min(low + 1, len(ordered) - 1)
    frac = idx - low
    return float(ordered[low] * (1.0 - frac) + ordered[high] * frac)


def format_float(v: float) -> str:
    return f"{v:.3f}"


def to_markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def analyze(run_dir: Path, top_n: int) -> tuple[list[dict[str, Any]], str]:
    metrics = load_json(run_dir / "metrics.json")
    episode_lookup = build_episode_lookup(metrics)
    memory_catalog = load_memory_catalog(run_dir)
    retrieve_records, episode_stats = scan_traces(run_dir, episode_lookup, memory_catalog)

    csv_rows: list[dict[str, Any]] = []
    md_lines: list[str] = []

    md_lines.append("# Memory Baseline Analysis")
    md_lines.append("")
    md_lines.append(f"- Generated at: {datetime.now(timezone.utc).isoformat()}")
    md_lines.append(f"- Run directory: `{run_dir}`")
    md_lines.append("")

    # 1) per-variant per-family metrics
    per_family_rows: list[list[Any]] = []
    for variant, eps in episode_lookup.items():
        families = defaultdict(list)
        for ep in eps.values():
            families[ep.task_family].append(ep)

        for family, family_eps in sorted(families.items()):
            scores = [e.score for e in family_eps]
            success_rate = mean([1.0 if e.success else 0.0 for e in family_eps])
            dep = mean([float(e.scheduling_scores.get("dependency_violation_rate", 0.0)) for e in family_eps])
            order = mean([float(e.scheduling_scores.get("order_violation_rate", 0.0)) for e in family_eps])
            miss = mean([float(e.scheduling_scores.get("missing_required_agent_rate", 0.0)) for e in family_eps])
            recover = mean([float(e.scheduling_scores.get("recovery_success_rate", 0.0)) for e in family_eps])
            unnecessary = mean([float(e.scheduling_scores.get("unnecessary_agent_calls", 0.0)) for e in family_eps])
            changed = int(sum(int(e.scheduling_scores.get("memory_changed_scheduling_decisions", 0)) for e in family_eps))
            support = int(sum(int(e.scheduling_scores.get("support_only_count", 0)) for e in family_eps))

            row = {
                "section": "per_family_metrics",
                "variant": variant,
                "task_family": family,
                "episode_count": len(family_eps),
                "success_rate": round(success_rate, 3),
                "mean_score": round(mean(scores), 3),
                "dependency_violation_rate": round(dep, 3),
                "order_violation_rate": round(order, 3),
                "missing_required_agent_rate": round(miss, 3),
                "recovery_success_rate": round(recover, 3),
                "unnecessary_agent_calls": round(unnecessary, 3),
                "memory_changed_scheduling_decisions": changed,
                "support_only_count": support,
            }
            csv_rows.append(row)

            per_family_rows.append(
                [
                    variant,
                    family,
                    len(family_eps),
                    format_float(success_rate),
                    format_float(mean(scores)),
                    format_float(order),
                    format_float(miss),
                    changed,
                ]
            )

    md_lines.append("## 1) Per-Variant Per-Family Metrics")
    md_lines.append("")
    md_lines.append(
        to_markdown_table(
            [
                "Variant",
                "Family",
                "Episodes",
                "Success Rate",
                "Mean Score",
                "Order Viol. Rate",
                "Missing Req. Rate",
                "Changed Decisions",
            ],
            per_family_rows,
        )
    )
    md_lines.append("")

    # 2) confusion matrices
    trigger_conf = Counter()
    source_conf = Counter()
    for rec in retrieve_records:
        trigger_conf[(rec.variant, rec.task_family, rec.trigger_task_family)] += 1
        source_key = rec.source_family if rec.source_family else rec.trigger_task_family
        source_conf[(rec.variant, rec.task_family, source_key)] += 1

    md_lines.append("## 2) Memory Trigger vs Task Family Confusion")
    md_lines.append("")

    for variant in sorted({r.variant for r in retrieve_records}):
        variant_rows = []
        for (v, task_family, trigger_family), count in sorted(trigger_conf.items()):
            if v != variant:
                continue
            csv_rows.append(
                {
                    "section": "confusion_matrix_trigger",
                    "variant": v,
                    "task_family": task_family,
                    "trigger_family": trigger_family,
                    "count": count,
                }
            )
            variant_rows.append([task_family, trigger_family, count])

        md_lines.append(f"### {variant} (trigger.task_family)")
        if variant_rows:
            md_lines.append(to_markdown_table(["Task Family", "Trigger Family", "Count"], variant_rows))
        else:
            md_lines.append("No retrieval records")
        md_lines.append("")

    md_lines.append("### Source-Family Lineage (if present)")
    lineage_rows = []
    for (variant, task_family, source_family), count in sorted(source_conf.items()):
        csv_rows.append(
            {
                "section": "confusion_matrix_source",
                "variant": variant,
                "task_family": task_family,
                "source_family": source_family,
                "count": count,
            }
        )
        lineage_rows.append([variant, task_family, source_family, count])
    if lineage_rows:
        md_lines.append(to_markdown_table(["Variant", "Task Family", "Source Family", "Count"], lineage_rows))
    else:
        md_lines.append("No source-family lineage found")
    md_lines.append("")

    # 3) top retrieved memories per family
    top_counter = Counter((r.variant, r.task_family, r.memory_id) for r in retrieve_records)
    top_rows = []
    for (variant, family, mem_id), count in top_counter.most_common(200):
        mem = memory_catalog.get(variant, {}).get(mem_id)
        trigger_family = mem.trigger_task_family if mem else "unknown"
        source_family = mem.source_family if mem else ""
        csv_rows.append(
            {
                "section": "top_retrieved_memory",
                "variant": variant,
                "task_family": family,
                "memory_id": mem_id,
                "trigger_family": trigger_family,
                "source_family": source_family,
                "count": count,
            }
        )

    # limit markdown to top per family
    by_vf = defaultdict(list)
    for (variant, family, mem_id), count in top_counter.items():
        by_vf[(variant, family)].append((count, mem_id))

    for (variant, family), items in sorted(by_vf.items()):
        items.sort(reverse=True)
        for count, mem_id in items[:3]:
            mem = memory_catalog.get(variant, {}).get(mem_id)
            top_rows.append(
                [
                    variant,
                    family,
                    mem_id,
                    mem.trigger_task_family if mem else "unknown",
                    mem.source_family if mem else "",
                    count,
                ]
            )

    md_lines.append("## 3) Top Retrieved Memory IDs / Triggers Per Family")
    md_lines.append("")
    if top_rows:
        md_lines.append(
            to_markdown_table(
                ["Variant", "Task Family", "Memory ID", "Trigger Family", "Source Family", "Count"],
                top_rows,
            )
        )
    else:
        md_lines.append("No retrieval records")
    md_lines.append("")

    # 4) influence type counts per family
    influence_by_family = Counter((r.variant, r.task_family, r.influence_type) for r in retrieve_records)
    influence_rows = []
    for (variant, family, influence), count in sorted(influence_by_family.items()):
        csv_rows.append(
            {
                "section": "influence_counts",
                "variant": variant,
                "task_family": family,
                "influence_type": influence,
                "count": count,
            }
        )
        influence_rows.append([variant, family, influence, count])

    md_lines.append("## 4) Influence Type Counts Per Family")
    md_lines.append("")
    if influence_rows:
        md_lines.append(to_markdown_table(["Variant", "Task Family", "Influence Type", "Count"], influence_rows))
    else:
        md_lines.append("No influence data")
    md_lines.append("")

    # 4b) eligibility and trigger-match diagnostics
    variant_keys = sorted(set(episode_lookup.keys()) | {v for (v, _) in episode_stats.keys()})
    eligibility_rows = []
    trigger_dist_rows = []

    for variant in variant_keys:
        variant_stats = [stats for (v, _), stats in episode_stats.items() if v == variant]
        retrieved_count = int(sum(s.retrieve_events for s in variant_stats))
        eligible_count = int(sum(s.eligible_count for s in variant_stats))
        blocked_count = int(sum(s.blocked_count for s in variant_stats))
        blocked_by_family_mismatch_count = int(
            sum(s.blocked_by_family_mismatch_count for s in variant_stats)
        )
        applied_changed_count = int(sum(s.applied_changed_count for s in variant_stats))
        support_only_count = int(sum(s.support_only_count for s in variant_stats))
        trigger_scores = [score for s in variant_stats for score in s.trigger_match_scores]

        csv_rows.append(
            {
                "section": "eligibility_summary",
                "variant": variant,
                "retrieved_count": retrieved_count,
                "eligible_count": eligible_count,
                "blocked_count": blocked_count,
                "blocked_by_family_mismatch_count": blocked_by_family_mismatch_count,
                "applied_changed_count": applied_changed_count,
                "support_only_count": support_only_count,
                "trigger_match_score_mean": round(mean(trigger_scores), 3),
                "trigger_match_score_min": round(min(trigger_scores), 3) if trigger_scores else 0.0,
                "trigger_match_score_p25": round(percentile(trigger_scores, 0.25), 3),
                "trigger_match_score_p50": round(percentile(trigger_scores, 0.50), 3),
                "trigger_match_score_p75": round(percentile(trigger_scores, 0.75), 3),
                "trigger_match_score_max": round(max(trigger_scores), 3) if trigger_scores else 0.0,
            }
        )

        eligibility_rows.append(
            [
                variant,
                retrieved_count,
                eligible_count,
                blocked_count,
                blocked_by_family_mismatch_count,
                applied_changed_count,
                support_only_count,
            ]
        )
        trigger_dist_rows.append(
            [
                variant,
                format_float(mean(trigger_scores)),
                format_float(percentile(trigger_scores, 0.25)),
                format_float(percentile(trigger_scores, 0.50)),
                format_float(percentile(trigger_scores, 0.75)),
                format_float(min(trigger_scores) if trigger_scores else 0.0),
                format_float(max(trigger_scores) if trigger_scores else 0.0),
            ]
        )

    md_lines.append("## 4b) Memory Eligibility Gate Diagnostics")
    md_lines.append("")
    if eligibility_rows:
        md_lines.append(
            to_markdown_table(
                [
                    "Variant",
                    "Retrieved",
                    "Eligible",
                    "Blocked",
                    "Blocked (Family Mismatch)",
                    "Applied Changed",
                    "Support Only",
                ],
                eligibility_rows,
            )
        )
    else:
        md_lines.append("No eligibility data")
    md_lines.append("")

    md_lines.append("### Trigger Match Score Distribution by Variant")
    md_lines.append("")
    if trigger_dist_rows:
        md_lines.append(
            to_markdown_table(
                ["Variant", "Mean", "P25", "P50", "P75", "Min", "Max"],
                trigger_dist_rows,
            )
        )
    else:
        md_lines.append("No trigger-match score data")
    md_lines.append("")

    # Episode comparison helpers
    no_eps = episode_lookup.get("mas_no_memory", {})
    orch_eps = episode_lookup.get("mas_orchestrator_memory", {})
    shuf_eps = episode_lookup.get("mas_shuffled_memory", {})

    # 5) examples where shuffled memory improved score (vs orchestrator)
    improved_examples = []
    for ep_idx in sorted(set(shuf_eps.keys()) & set(orch_eps.keys())):
        sh = shuf_eps[ep_idx]
        oc = orch_eps[ep_idx]
        delta = sh.score - oc.score
        if delta <= 0:
            continue

        stats = episode_stats.get(("mas_shuffled_memory", ep_idx), EpisodeTraceStats())
        top_mem = stats.memory_counter.most_common(1)
        top_mem_id = top_mem[0][0] if top_mem else ""
        mem_meta = memory_catalog.get("mas_shuffled_memory", {}).get(top_mem_id)

        improved_examples.append(
            {
                "episode_idx": ep_idx,
                "task_family": sh.task_family,
                "shuffled_score": sh.score,
                "orchestrator_score": oc.score,
                "delta_vs_orchestrator": delta,
                "retrieve_events": stats.retrieve_events,
                "top_memory_id": top_mem_id,
                "top_trigger_family": mem_meta.trigger_task_family if mem_meta else "",
                "top_source_family": mem_meta.source_family if mem_meta else "",
                "influence_counts": dict(stats.influence_counts),
            }
        )

    improved_examples.sort(key=lambda x: x["delta_vs_orchestrator"], reverse=True)
    md_lines.append("## 5) Examples Where Shuffled Memory Improved Score")
    md_lines.append("")
    if improved_examples:
        rows = []
        for ex in improved_examples[:top_n]:
            csv_rows.append({"section": "shuffled_improved", **ex})
            rows.append(
                [
                    ex["episode_idx"],
                    ex["task_family"],
                    format_float(ex["shuffled_score"]),
                    format_float(ex["orchestrator_score"]),
                    format_float(ex["delta_vs_orchestrator"]),
                    ex["top_memory_id"],
                    ex["top_trigger_family"],
                    ex["top_source_family"],
                ]
            )
        md_lines.append(
            to_markdown_table(
                [
                    "Episode",
                    "Family",
                    "Shuffled",
                    "Orchestrator",
                    "Delta",
                    "Top Memory",
                    "Trigger",
                    "Source",
                ],
                rows,
            )
        )
    else:
        md_lines.append("No improved examples found")
    md_lines.append("")

    # 6) examples where shuffled caused negative transfer (vs no_memory)
    negative_examples = []
    for ep_idx in sorted(set(shuf_eps.keys()) & set(no_eps.keys())):
        sh = shuf_eps[ep_idx]
        nm = no_eps[ep_idx]
        delta = sh.score - nm.score
        if delta >= 0:
            continue

        stats = episode_stats.get(("mas_shuffled_memory", ep_idx), EpisodeTraceStats())
        if stats.retrieve_events <= 0:
            continue

        top_mem = stats.memory_counter.most_common(1)
        top_mem_id = top_mem[0][0] if top_mem else ""
        mem_meta = memory_catalog.get("mas_shuffled_memory", {}).get(top_mem_id)

        negative_examples.append(
            {
                "episode_idx": ep_idx,
                "task_family": sh.task_family,
                "shuffled_score": sh.score,
                "no_memory_score": nm.score,
                "delta_vs_no_memory": delta,
                "retrieve_events": stats.retrieve_events,
                "top_memory_id": top_mem_id,
                "top_trigger_family": mem_meta.trigger_task_family if mem_meta else "",
                "top_source_family": mem_meta.source_family if mem_meta else "",
                "influence_counts": dict(stats.influence_counts),
            }
        )

    negative_examples.sort(key=lambda x: x["delta_vs_no_memory"])
    md_lines.append("## 6) Examples Where Shuffled Memory Caused Negative Transfer")
    md_lines.append("")
    if negative_examples:
        rows = []
        for ex in negative_examples[:top_n]:
            csv_rows.append({"section": "shuffled_negative_transfer", **ex})
            rows.append(
                [
                    ex["episode_idx"],
                    ex["task_family"],
                    format_float(ex["shuffled_score"]),
                    format_float(ex["no_memory_score"]),
                    format_float(ex["delta_vs_no_memory"]),
                    ex["top_memory_id"],
                    ex["top_trigger_family"],
                    ex["top_source_family"],
                ]
            )
        md_lines.append(
            to_markdown_table(
                [
                    "Episode",
                    "Family",
                    "Shuffled",
                    "No Memory",
                    "Delta",
                    "Top Memory",
                    "Trigger",
                    "Source",
                ],
                rows,
            )
        )
    else:
        md_lines.append("No negative-transfer examples found")
    md_lines.append("")

    # 7) permissiveness assessment
    permissive_rows = []
    for variant in sorted({r.variant for r in retrieve_records}):
        var_records = [r for r in retrieve_records if r.variant == variant]
        total_refs = len(var_records)
        trigger_mismatch = sum(1 for r in var_records if r.trigger_task_family != r.task_family)
        source_labeled = [r for r in var_records if r.source_family]
        source_mismatch = sum(1 for r in source_labeled if r.source_family != r.task_family)

        trigger_mismatch_rate = (trigger_mismatch / total_refs) if total_refs else 0.0
        source_mismatch_rate = (source_mismatch / len(source_labeled)) if source_labeled else 0.0

        verdict = "likely_not_permissive"
        reason = "Task-family trigger mostly aligned"
        if source_labeled and source_mismatch_rate > 0.5:
            verdict = "too_permissive_by_content"
            reason = "Retrieved memories often originate from different source_family while still matching by task_family trigger"
        elif trigger_mismatch_rate > 0.25:
            verdict = "too_permissive_by_trigger"
            reason = "High trigger-task mismatch in retrieved refs"

        row = {
            "section": "matching_permissiveness",
            "variant": variant,
            "total_retrieved_refs": total_refs,
            "trigger_mismatch_refs": trigger_mismatch,
            "trigger_mismatch_rate": round(trigger_mismatch_rate, 3),
            "source_labeled_refs": len(source_labeled),
            "source_mismatch_refs": source_mismatch,
            "source_mismatch_rate": round(source_mismatch_rate, 3),
            "verdict": verdict,
            "reason": reason,
        }
        csv_rows.append(row)
        permissive_rows.append(
            [
                variant,
                total_refs,
                f"{trigger_mismatch}/{total_refs}" if total_refs else "0/0",
                format_float(trigger_mismatch_rate),
                f"{source_mismatch}/{len(source_labeled)}" if source_labeled else "0/0",
                format_float(source_mismatch_rate),
                verdict,
                reason,
            ]
        )

    md_lines.append("## 7) Is Memory Matching Too Permissive?")
    md_lines.append("")
    md_lines.append(
        to_markdown_table(
            [
                "Variant",
                "Retrieved Refs",
                "Trigger Mismatch",
                "Trigger Mismatch Rate",
                "Source Mismatch",
                "Source Mismatch Rate",
                "Verdict",
                "Reason",
            ],
            permissive_rows,
        )
    )
    md_lines.append("")

    # direct explanation focus for user question
    if "mas_shuffled_memory" in metrics and "mas_orchestrator_memory" in metrics:
        sh = metrics["mas_shuffled_memory"]
        oc = metrics["mas_orchestrator_memory"]
        md_lines.append("## Why Shuffled Can Outscore Orchestrator Here")
        md_lines.append("")
        md_lines.append(
            f"- `mas_shuffled_memory.mean_score={sh.get('mean_score')}` vs `mas_orchestrator_memory.mean_score={oc.get('mean_score')}`."
        )
        md_lines.append(
            "- Current retrieval matching keys primarily on `trigger.task_family`; shuffled seeds can still match the same family even when `source_family` differs."
        )
        md_lines.append(
            "- Several shuffled memories carry generic schedules/avoid rules that accidentally help hard-family penalties (especially ordering penalties), producing positive transfer in some episodes."
        )
        md_lines.append(
            "- Orchestrator-memory run mixes seeded + curated memories, and curation may reinforce suboptimal but high-confidence patterns for some families, reducing relative score on this run."
        )
        md_lines.append("")

    markdown = "\n".join(md_lines) + "\n"
    return csv_rows, markdown


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        raise ValueError("No analysis rows to write")

    all_keys = sorted({k for row in rows for k in row.keys()})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir or detect_latest_run(args.experiments_dir)
    csv_out = args.csv_out or (run_dir / "memory_baseline_analysis.csv")
    md_out = args.md_out or (run_dir / "memory_baseline_analysis.md")

    rows, markdown = analyze(run_dir=run_dir, top_n=max(1, args.top_n))
    write_csv(rows, csv_out)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(markdown, encoding="utf-8")

    print(f"Run dir: {run_dir}")
    print(f"CSV written: {csv_out}")
    print(f"Markdown written: {md_out}")


if __name__ == "__main__":
    main()
