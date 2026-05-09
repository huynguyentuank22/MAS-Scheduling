"""End-to-end and orchestrator behavior tests."""

import json
import shutil
import tempfile
from pathlib import Path

from olm_mas.agent_registry import AgentRegistry
from olm_mas.agent_runtime import AgentRuntime
from olm_mas.benchmark_runner import BenchmarkRunner, generate_episodes
from olm_mas.blackboard import Blackboard
from olm_mas.evaluator import SchedulingEvaluator
from olm_mas.memory_curator import MemoryCurator
from olm_mas.memory_store import MemoryStore
from olm_mas.orchestrator import Orchestrator
from olm_mas.policy_engine import PolicyEngine
from olm_mas.schemas import ProceduralControlMemory
from olm_mas.trace_logger import TraceLogger


def _make_orchestrator(
    output_dir: Path,
    use_memory: bool = False,
    use_curation: bool = False,
    memory_store: MemoryStore | None = None,
    blackboard: Blackboard | None = None,
) -> tuple[Orchestrator, MemoryStore, Blackboard]:
    store = memory_store or MemoryStore()
    bb = blackboard or Blackboard()
    curator = MemoryCurator(store) if use_curation else None

    orchestrator = Orchestrator(
        registry=AgentRegistry(),
        runtime=AgentRuntime(seed=42, failure_rate=0.0),
        memory_store=store,
        blackboard=bb,
        policy_engine=PolicyEngine(),
        trace_logger=TraceLogger(trace_dir=str(output_dir / "traces")),
        evaluator=SchedulingEvaluator(),
        curator=curator,
        use_memory=use_memory,
    )
    return orchestrator, store, bb


def test_generate_episodes():
    episodes = generate_episodes(10, seed=42)
    assert len(episodes) == 10
    assert all("task_family" in ep for ep in episodes)
    assert all("tasks" in ep for ep in episodes)
    families = [ep["task_family"] for ep in episodes]
    assert len(set(families)) < 10


def test_small_synthetic_run():
    """Run a minimal ablation with 5 episodes and check outputs."""
    config = {
        "experiment": {
            "name": "test_synthetic",
            "benchmark": "synthetic",
            "num_episodes": 5,
            "split": {"accumulation": 3, "test": 2},
            "random_seed": 42,
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
            },
        },
    }

    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_test_"))
    config_path = output_dir / "test_config.yaml"

    try:
        import yaml

        config_path.write_text(yaml.dump(config), encoding="utf-8")

        runner = BenchmarkRunner(
            config_path=str(config_path),
            output_dir=str(output_dir),
        )
        result = runner.run()

        assert "results" in result
        assert "mas_no_memory" in result["results"]
        assert "mas_orchestrator_memory" in result["results"]

        metrics_path = output_dir / "metrics.json"
        assert metrics_path.exists()
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        assert "mas_no_memory" in metrics
        assert "mas_orchestrator_memory" in metrics

        comparison_path = output_dir / "comparison_report.json"
        assert comparison_path.exists()
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        assert "delta" in comparison

        trace_dir = output_dir / "traces"
        assert trace_dir.exists()
        no_mem_traces = list((trace_dir / "mas_no_memory").glob("*.jsonl"))
        with_mem_traces = list((trace_dir / "mas_orchestrator_memory").glob("*.jsonl"))
        assert len(no_mem_traces) > 0
        assert len(with_mem_traces) > 0

        trace_file = no_mem_traces[0]
        lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            record = json.loads(line)
            assert "_type" in record

        no_mem_summary = result["results"]["mas_no_memory"]
        assert "success_rate" in no_mem_summary
        assert "mean_score" in no_mem_summary
        assert "episodes" in no_mem_summary
        assert len(no_mem_summary["episodes"]) == 5

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_orchestrator_single_episode():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_test_"))

    try:
        orchestrator, _, _ = _make_orchestrator(output_dir=output_dir)
        result = orchestrator.run_episode(
            objective="Test single episode",
            task_descriptions=["Plan the work", "Research the topic", "Write the report"],
            task_family="research_report",
        )

        assert result["workflow"].status.value in ("completed", "failed")
        assert len(result["decisions"]) > 0
        assert result["evaluation"].workflow_id == result["workflow"].workflow_id

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_episode_reflection_created():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_test_"))

    try:
        orchestrator, store, _ = _make_orchestrator(
            output_dir=output_dir,
            use_curation=True,
        )
        result = orchestrator.run_episode(
            objective="Reflection test",
            task_descriptions=["Plan", "Research", "Write"],
            task_family="reflection_family",
        )

        reflections = store.list_reflections(workflow_id=result["workflow"].workflow_id)
        assert len(reflections) == 1

        reflection = reflections[0]
        assert reflection.workflow_id == result["workflow"].workflow_id
        assert reflection.outcome in ("success", "failure")
        assert isinstance(reflection.reward_or_score, float)
        assert isinstance(reflection.learned_memory_refs, list)

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_decision_latency_populated():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_test_"))

    try:
        orchestrator, _, _ = _make_orchestrator(output_dir=output_dir)
        result = orchestrator.run_episode(
            objective="Latency test",
            task_descriptions=["Plan the work", "Research sources", "Write summary"],
            task_family="research_report",
        )

        call_decisions = [
            d
            for d in result["decisions"]
            if d.chosen_action in ("call_agent", "call_recovery_agent")
        ]
        assert call_decisions
        assert all(d.latency_sec is not None for d in call_decisions)
        assert all(d.cost is not None for d in call_decisions)

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_retrieve_memory_decision_logged():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_test_"))

    try:
        store = MemoryStore()
        mem = ProceduralControlMemory(
            trigger={"task_family": "research_report"},
            recommended_schedule=["planner", "researcher", "writer", "critic"],
            confidence=0.9,
        )
        store.put_procedural(mem)

        orchestrator, _, _ = _make_orchestrator(
            output_dir=output_dir,
            use_memory=True,
            memory_store=store,
        )
        result = orchestrator.run_episode(
            objective="Memory retrieval decision test",
            task_descriptions=["Write the summary"],
            task_family="research_report",
        )

        actions = [d.chosen_action for d in result["decisions"]]
        assert "retrieve_memory" in actions

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_memory_influence_metadata_logged():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_test_"))

    try:
        store = MemoryStore()
        mem = ProceduralControlMemory(
            trigger={"task_family": "research_report"},
            avoid=[{"action": "writer_before_critic"}],
            confidence=0.9,
        )
        store.put_procedural(mem)

        orchestrator, _, _ = _make_orchestrator(
            output_dir=output_dir,
            use_memory=True,
            memory_store=store,
        )
        result = orchestrator.run_episode(
            objective="Memory influence metadata test",
            task_descriptions=["Write the summary"],
            task_family="research_report",
        )

        retrieve_events = [d for d in result["decisions"] if d.chosen_action == "retrieve_memory"]
        call_events = [d for d in result["decisions"] if d.chosen_action == "call_agent"]
        assert retrieve_events
        assert call_events

        retrieve_meta = retrieve_events[0].memory_influence
        call_meta = call_events[0].memory_influence
        expected_keys = {
            "used",
            "memory_id",
            "influence_type",
            "baseline_action",
            "baseline_agent",
            "final_action",
            "final_agent",
            "reason",
        }
        assert expected_keys.issubset(set(retrieve_meta.keys()))
        assert expected_keys.issubset(set(call_meta.keys()))
        assert retrieve_meta["used"] is True
        assert call_meta["used"] is True
        assert call_meta["influence_type"] in {
            "support_only",
            "changed_agent_selection",
            "changed_ordering",
            "changed_recovery",
        }

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_blackboard_isolation_across_episodes():
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_test_"))

    try:
        shared_blackboard = Blackboard()
        orchestrator, _, blackboard = _make_orchestrator(
            output_dir=output_dir,
            blackboard=shared_blackboard,
        )

        ep1 = orchestrator.run_episode(
            objective="Episode 1",
            task_descriptions=["Plan", "Research", "Write"],
            task_family="family_a",
        )
        wf1 = ep1["workflow"].workflow_id
        assert any(a.workflow_id == wf1 for a in blackboard.list_artifacts())

        ep2 = orchestrator.run_episode(
            objective="Episode 2",
            task_descriptions=["Plan", "Research", "Write"],
            task_family="family_b",
        )
        wf2 = ep2["workflow"].workflow_id

        artifacts_after_ep2 = blackboard.list_artifacts()
        assert artifacts_after_ep2
        assert all(a.workflow_id == wf2 for a in artifacts_after_ep2)
        assert all(a.workflow_id != wf1 for a in artifacts_after_ep2)

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)
