"""Smoke tests for external benchmark adapter integration."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from olm_mas.benchmarks.gaia_lite import GAIALiteAdapter, get_gaia_lite_seed_memories
from olm_mas.external_benchmark_runner import ExternalBenchmarkRunner


def test_adapter_loads_sample_tasks():
    adapter = GAIALiteAdapter()
    tasks = adapter.load_tasks(split="sample", limit=5)
    assert len(tasks) == 5
    assert all("task_id" in task for task in tasks)
    assert all("question" in task for task in tasks)


def test_adapter_metadata_includes_required_fields():
    adapter = GAIALiteAdapter()
    task = adapter.load_tasks(split="sample", limit=1)[0]
    meta = adapter.get_task_metadata(task)
    assert meta["benchmark"] == "gaia_lite"
    assert isinstance(meta["task_family"], str) and meta["task_family"]
    assert isinstance(meta["task_pattern"], str)
    assert isinstance(meta["constraints"], dict)


def test_seeded_memories_match_gaia_lite_triggers():
    seeds = get_gaia_lite_seed_memories()
    required_families = {
        "numeric_reasoning",
        "web_research",
        "multi_hop",
        "file_question",
        "verification_heavy",
    }
    assert required_families.issubset(set(seeds.keys()))
    for family in required_families:
        trigger = seeds[family]["trigger"]
        assert trigger["benchmark"] == "gaia_lite"
        assert trigger["task_family"] == family

    assert seeds["numeric_reasoning"]["recommended_schedule"] == [
        "planner",
        "tool_executor",
        "calculator",
        "verifier",
    ]
    assert seeds["web_research"]["recommended_schedule"] == [
        "planner",
        "researcher",
        "writer",
        "verifier",
    ]
    assert seeds["multi_hop"]["recommended_schedule"] == [
        "planner",
        "researcher",
        "critic",
        "writer",
        "verifier",
    ]
    assert seeds["file_question"]["recommended_schedule"] == [
        "planner",
        "file_reader",
        "writer",
        "verifier",
    ]


def test_benchmark_run_creates_traces_metrics_and_validation_report():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_gaia_smoke_"))
    runner = ExternalBenchmarkRunner(
        benchmark_name="gaia_lite",
        split="sample",
        limit=5,
        variant="mas_orchestrator_memory",
        output_dir=str(output_dir),
        seed=123,
    )
    result = runner.run()

    assert "results" in result
    assert "mas_orchestrator_memory" in result["results"]

    metrics_path = output_dir / "metrics.json"
    validation_csv = output_dir / "validation_metrics_report.csv"
    validation_md = output_dir / "validation_metrics_report.md"
    trace_dir = output_dir / "traces" / "mas_orchestrator_memory"

    assert metrics_path.exists()
    assert validation_csv.exists()
    assert validation_md.exists()
    assert trace_dir.exists()
    assert len(list(trace_dir.glob("*.jsonl"))) > 0

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    summary = metrics["mas_orchestrator_memory"]
    assert summary["benchmark"] == "gaia_lite"
    assert summary["split"] == "sample"
    assert summary["total_tasks"] == 5
