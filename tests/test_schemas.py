"""Tests for Pydantic schemas — creation, validation, serialization."""

import json
from datetime import datetime, timezone

from olm_mas.schemas import (
    AgentProfile,
    Artifact,
    ArtifactStatus,
    CurationAction,
    DecisionEvent,
    EpisodeReflection,
    ExecutionTraceEvent,
    MemoryStatus,
    PolicyRule,
    ProceduralControlMemory,
    SchedulingAction,
    SchedulingEvaluation,
    TaskNode,
    TaskState,
    WorkflowSession,
    WorkflowStatus,
)


def test_workflow_session_defaults():
    wf = WorkflowSession(objective="Test task")
    assert wf.workflow_id  # auto-generated
    assert wf.objective == "Test task"
    assert wf.status == WorkflowStatus.CREATED
    assert wf.current_plan_version == 1
    assert isinstance(wf.created_at, datetime)


def test_workflow_session_serialization():
    wf = WorkflowSession(objective="Serialize me")
    data = json.loads(wf.model_dump_json())
    assert data["objective"] == "Serialize me"
    assert data["status"] == "created"


def test_task_node_defaults():
    task = TaskNode(description="Do something", workflow_id="wf-1")
    assert task.task_id
    assert task.state == TaskState.PENDING
    assert task.retry_count == 0
    assert task.depends_on == []


def test_task_node_with_dependencies():
    task = TaskNode(
        description="Step 2",
        workflow_id="wf-1",
        depends_on=["task-1"],
        priority=0.8,
    )
    assert task.depends_on == ["task-1"]
    assert task.priority == 0.8


def test_agent_profile():
    profile = AgentProfile(
        agent_type="planner",
        capability_tags=["planning", "decomposition"],
        trust_score=0.75,
    )
    assert profile.agent_type == "planner"
    assert "planning" in profile.capability_tags
    assert profile.trust_score == 0.75


def test_policy_rule_hard_constraint():
    rule = PolicyRule(
        subject_scope="*",
        object_scope="external_send",
        action="deny",
        is_hard_constraint=True,
    )
    assert rule.is_hard_constraint is True
    assert rule.action == "deny"


def test_artifact_defaults():
    art = Artifact(
        workflow_id="wf-1",
        artifact_type="evidence",
        content={"finding": "test"},
        created_by="researcher",
    )
    assert art.status == ArtifactStatus.DRAFT
    assert art.version == 1


def test_decision_event():
    event = DecisionEvent(
        workflow_id="wf-1",
        chosen_action="call_agent",
        rationale_summary="Schedule researcher for evidence gathering",
    )
    assert event.decision_id
    assert event.chosen_action == "call_agent"


def test_execution_trace_event():
    event = ExecutionTraceEvent(
        workflow_id="wf-1",
        event_type="agent_call",
        actor="researcher",
    )
    assert event.event_id
    assert event.event_type == "agent_call"


def test_scheduling_action():
    action = SchedulingAction(
        action_type="call_agent",
        agent_template="researcher",
        task_id="task-1",
        rationale="Assign researcher",
    )
    assert action.action_type == "call_agent"


def test_scheduling_evaluation():
    ev = SchedulingEvaluation(
        workflow_id="wf-1",
        benchmark_success=True,
        benchmark_score=0.95,
    )
    assert ev.benchmark_success is True
    assert ev.useful_memory_refs == []


def test_episode_reflection():
    ref = EpisodeReflection(
        workflow_id="wf-1",
        outcome="success",
        reward_or_score=0.9,
    )
    assert ref.outcome == "success"


def test_procedural_control_memory():
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        recommended_schedule=["planner", "researcher", "writer", "critic"],
        confidence=0.7,
        status=MemoryStatus.ACTIVE,
    )
    assert mem.memory_id
    assert mem.confidence == 0.7
    assert "planner" in mem.recommended_schedule


def test_curation_action_enum():
    assert CurationAction.CREATE.value == "CREATE"
    assert CurationAction.DEPRECATE.value == "DEPRECATE"


def test_round_trip_serialization():
    """Test full serialization round-trip for a complex model."""
    mem = ProceduralControlMemory(
        trigger={"task_family": "data_analysis", "tags": ["data"]},
        recommended_schedule=["planner", "researcher"],
        avoid=[{"action": "retry", "reason": "not effective"}],
        confidence=0.65,
    )
    json_str = mem.model_dump_json()
    restored = ProceduralControlMemory.model_validate_json(json_str)
    assert restored.memory_id == mem.memory_id
    assert restored.confidence == mem.confidence
    assert restored.avoid == mem.avoid
