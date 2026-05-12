"""LLM-readiness validation tests for runtime parsing and memory curation."""

import tempfile
from pathlib import Path

from olm_mas.agent_registry import AgentRegistry
from olm_mas.agent_runtime import AgentRuntime, NoisyLLMRuntime
from olm_mas.blackboard import Blackboard
from olm_mas.evaluator import SchedulingEvaluator
from olm_mas.llm_output_parser import LLMOutputParser
from olm_mas.memory_curator import MemoryCurator
from olm_mas.memory_extraction_validator import MemoryExtractionValidator
from olm_mas.memory_store import MemoryStore
from olm_mas.orchestrator import Orchestrator
from olm_mas.policy_engine import PolicyEngine
from olm_mas.schemas import (
    CurationAction,
    ProceduralControlMemory,
    SchedulingEvaluation,
    WorkflowSession,
)
from olm_mas.trace_logger import TraceLogger


def _make_orchestrator_with_runtime(
    runtime,
    use_curation: bool = True,
) -> tuple[Orchestrator, MemoryStore]:
    output_dir = Path(tempfile.mkdtemp(prefix="olm_mas_llm_"))
    store = MemoryStore()
    registry = AgentRegistry()
    curator = MemoryCurator(store, agent_registry=registry) if use_curation else None
    orchestrator = Orchestrator(
        registry=registry,
        runtime=runtime,
        memory_store=store,
        blackboard=Blackboard(),
        policy_engine=PolicyEngine(),
        trace_logger=TraceLogger(trace_dir=str(output_dir / "traces")),
        evaluator=SchedulingEvaluator(),
        curator=curator,
        use_memory=False,
        max_steps=10,
    )
    return orchestrator, store


def test_malformed_llm_output_repaired_once():
    parser = LLMOutputParser()
    raw = (
        '{"status":"success","summary":"ok","artifact_type":"draft",'
        '"artifact_payload":{"text":"hello",},"confidence":0.8,"uncertainties":[]}'
    )
    parsed = parser.parse(raw)
    assert parsed.schema_valid is True
    assert parsed.repair_attempt_count == 1
    assert parser.last_metrics["repair_attempted"] is True
    assert parser.last_metrics["repair_succeeded"] is True


def test_malformed_output_after_repair_is_invalid():
    parser = LLMOutputParser()
    parsed = parser.parse("this is not json")
    assert parsed.schema_valid is False
    assert parsed.status.value == "invalid"
    assert parsed.repair_attempt_count == 1
    assert any("malformed_json_after_repair" in e for e in parsed.validation_errors)


def test_invalid_output_cannot_create_procedural_memory():
    curator = MemoryCurator(memory_store=MemoryStore(), agent_registry=AgentRegistry())
    wf = WorkflowSession(objective="x", task_family="research_report", benchmark_name="synthetic")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=True,
        benchmark_score=1.0,
        scheduling_scores={
            "agent_assignment_quality": 1.0,
            "agent_output_schema_valid_rate": 0.5,
            "parse_failure_rate": 0.2,
        },
    )
    actions = curator.curate(wf, ev, decisions=[])
    assert any(item["action"] == CurationAction.IGNORE for item in actions)
    assert any("invalid_agent_output_blocks_memory_update" in item["reason"] for item in actions)


def test_hallucinated_artifact_ref_is_rejected():
    runtime = NoisyLLMRuntime(seed=42, failure_rate=0.0, noise_mode="hallucinated_artifact_ref")
    profile = AgentRegistry().get("writer")
    assert profile is not None
    result = runtime.run(profile=profile, task_description="Write output")
    output = result["agent_output"]
    assert output.schema_valid is False
    assert any("runtime_field_not_allowed:artifact_id" in e for e in output.validation_errors)
    assert "artifact_id" in set(result["parse_meta"].get("invalid_runtime_fields") or [])


def test_unsupported_lesson_rejected_by_memory_validator():
    validator = MemoryExtractionValidator()
    registry = AgentRegistry()
    wf = WorkflowSession(objective="x", task_family="research_report", benchmark_name="synthetic")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=True,
        scheduling_scores={"agent_output_schema_valid_rate": 1.0, "parse_failure_rate": 0.0},
        failure_factors=[],
    )
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report", "benchmark": "synthetic"},
        recommended_schedule=["planner", "researcher", "writer", "critic"],
        avoid=[{"action": "never_seen_pattern"}],
        confidence=0.7,
        supporting_episodes=[wf.workflow_id],
    )
    result = validator.validate(mem, wf, ev, decisions=[], registry=registry)
    assert result["accepted"] is False
    assert result["unsupported"] is True


def test_overgeneralized_memory_rejected():
    validator = MemoryExtractionValidator()
    registry = AgentRegistry()
    wf = WorkflowSession(objective="x", task_family="research_report")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=True,
        scheduling_scores={"agent_output_schema_valid_rate": 1.0, "parse_failure_rate": 0.0},
    )
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        recommended_schedule=["critic", "writer"],
        confidence=0.8,
        supporting_episodes=[wf.workflow_id],
    )
    result = validator.validate(mem, wf, ev, decisions=[], registry=registry)
    assert result["accepted"] is False
    assert result["overgeneralized"] is True


def test_valid_llm_like_output_can_create_memory():
    orchestrator, store = _make_orchestrator_with_runtime(
        runtime=AgentRuntime(seed=42, failure_rate=0.0),
        use_curation=True,
    )
    result = orchestrator.run_episode(
        objective="Create memory from valid run",
        task_descriptions=["Plan", "Research", "Write"],
        benchmark_name="synthetic",
        task_family="novel_family",
    )
    assert result["workflow"].workflow_id
    assert any(item["action"] == CurationAction.CREATE for item in result["curation_actions"])
    assert any(m.trigger.get("task_family") == "novel_family" for m in store.list_procedural())


def test_runtime_owned_fields_cannot_be_overridden():
    parser = LLMOutputParser()
    raw = {
        "status": "success",
        "summary": "Injected runtime fields",
        "artifact_type": "draft",
        "artifact_payload": {"text": "hello"},
        "confidence": 0.8,
        "uncertainties": [],
        "workflow_id": "fake-wf",
        "task_id": "fake-task",
        "decision_id": "fake-decision",
        "artifact_id": "fake-artifact",
    }
    parsed = parser.parse(raw)
    assert parsed.schema_valid is False
    assert any("runtime_field_not_allowed:workflow_id" in e for e in parsed.validation_errors)
    assert any("runtime_field_not_allowed:artifact_id" in e for e in parsed.validation_errors)


def test_orchestrator_does_not_crash_on_noisy_outputs():
    for mode in [
        "malformed_json",
        "missing_fields",
        "hallucinated_artifact_ref",
        "overgeneralized_lesson",
    ]:
        orchestrator, _ = _make_orchestrator_with_runtime(
            runtime=NoisyLLMRuntime(seed=42, failure_rate=0.0, noise_mode=mode),
            use_curation=True,
        )
        result = orchestrator.run_episode(
            objective=f"Noisy mode {mode}",
            task_descriptions=["Plan", "Research", "Write"],
            benchmark_name="synthetic",
            task_family="research_report",
        )
        assert result["workflow"].workflow_id
        assert isinstance(result["decisions"], list)
