"""Tests for the Scheduler — decision correctness."""

from olm_mas.agent_registry import AgentRegistry
from olm_mas.memory_store import MemoryStore
from olm_mas.scheduler import Scheduler
from olm_mas.schemas import (
    ProceduralControlMemory,
    TaskNode,
    TaskState,
    WorkflowSession,
)


def _make_scheduler(use_memory: bool = False) -> tuple[Scheduler, MemoryStore]:
    registry = AgentRegistry()
    store = MemoryStore()
    scheduler = Scheduler(
        registry=registry,
        memory_store=store,
        use_memory=use_memory,
    )
    return scheduler, store


def test_finalize_when_all_done():
    scheduler, _ = _make_scheduler()
    wf = WorkflowSession(objective="test")
    tasks = [
        TaskNode(workflow_id=wf.workflow_id, description="Task 1", state=TaskState.DONE),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "finalize"


def test_schedule_pending_task():
    scheduler, _ = _make_scheduler()
    wf = WorkflowSession(objective="test")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Research the topic",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "call_agent"
    assert action.agent_template == "researcher"


def test_keyword_agent_mapping():
    scheduler, _ = _make_scheduler()
    wf = WorkflowSession(objective="test")

    # "plan" -> planner
    tasks = [TaskNode(workflow_id=wf.workflow_id, description="Plan the approach")]
    assert scheduler.next_action(wf, tasks).agent_template == "planner"

    # "verify" -> critic
    tasks = [TaskNode(workflow_id=wf.workflow_id, description="Verify the results")]
    assert scheduler.next_action(wf, tasks).agent_template == "critic"

    # "write" -> writer
    tasks = [TaskNode(workflow_id=wf.workflow_id, description="Write the report")]
    assert scheduler.next_action(wf, tasks).agent_template == "writer"


def test_retry_failed_task():
    scheduler, _ = _make_scheduler()
    wf = WorkflowSession(objective="test")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Do something",
            state=TaskState.FAILED,
            retry_count=0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "retry"


def test_recovery_after_max_retries():
    scheduler, _ = _make_scheduler()
    wf = WorkflowSession(objective="test")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Do something",
            state=TaskState.FAILED,
            retry_count=2,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "call_recovery_agent"
    assert action.agent_template == "recovery"


def test_dependency_respect():
    scheduler, _ = _make_scheduler()
    wf = WorkflowSession(objective="test")
    t1 = TaskNode(
        workflow_id=wf.workflow_id,
        description="First task",
        state=TaskState.PENDING,
    )
    t2 = TaskNode(
        workflow_id=wf.workflow_id,
        description="Second task depends on first",
        state=TaskState.PENDING,
        depends_on=[t1.task_id],
    )
    # Only t1 should be schedulable
    action = scheduler.next_action(wf, [t1, t2])
    assert action.task_id == t1.task_id


def test_memory_refs_included_when_enabled():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        recommended_schedule=["planner", "researcher"],
        confidence=0.8,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="research_report")
    tasks = [
        TaskNode(workflow_id=wf.workflow_id, description="Research something"),
    ]
    action = scheduler.next_action(wf, tasks)
    assert mem.memory_id in action.memory_refs


def test_memory_informed_agent_selection():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        # Baseline writer should still be selected with memory support.
        recommended_schedule=["writer", "critic"],
        confidence=0.9,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="research_report")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write the final draft",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "call_agent"
    assert action.agent_template == "writer"
    assert action.memory_influence["influence_type"] == "support_only"


def test_memory_changes_writer_to_critic_when_critic_prerequisite_missing():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report", "benchmark": "synthetic"},
        avoid=[{"action": "writer_before_critic"}],
        confidence=0.9,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="research_report", benchmark_name="synthetic")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write the final draft",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "call_agent"
    assert action.agent_template == "critic"
    assert action.memory_influence["influence_type"] == "changed_agent_selection"


def test_memory_marks_support_only_when_memory_agrees_with_baseline():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        recommended_schedule=["writer", "critic"],
        confidence=0.8,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="research_report")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write report summary",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.agent_template == "writer"
    assert action.memory_influence["used"] is True
    assert action.memory_influence["influence_type"] == "support_only"
    assert action.memory_influence["baseline_agent"] == "writer"
    assert action.memory_influence["final_agent"] == "writer"


def test_memory_changes_finalize_to_verifier_when_verifier_required():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report", "benchmark": "synthetic"},
        avoid=[{"action": "finalize_without_verifier"}],
        confidence=0.85,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="research_report", benchmark_name="synthetic")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write draft",
            state=TaskState.DONE,
            assigned_agent="writer",
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "call_agent"
    assert action.agent_template == "critic"
    assert action.memory_influence["influence_type"] == "changed_ordering"


def test_memory_changes_retry_to_recovery_when_recovery_rule_matches():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report", "benchmark": "synthetic"},
        recommended_recovery=[
            {
                "when_action": "retry",
                "min_retry_count": 1,
                "action": "recovery_agent",
                "reason": "Escalate after one retry",
            }
        ],
        confidence=0.9,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="research_report", benchmark_name="synthetic")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write report",
            state=TaskState.FAILED,
            assigned_agent="writer",
            retry_count=1,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "call_recovery_agent"
    assert action.agent_template == "recovery"
    assert action.memory_influence["influence_type"] == "changed_recovery"


def test_cross_family_memory_cannot_change_scheduling():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={
            "task_family": "multi_source_conflict",
            "benchmark": "synthetic",
            "source_family": "debugging",
        },
        avoid=[{"action": "writer_before_critic"}],
        confidence=0.95,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="multi_source_conflict", benchmark_name="synthetic")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write the final merged summary",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.agent_template == "writer"
    assert action.memory_influence["influence_type"] == "none"
    assert action.memory_influence["eligible_to_influence"] is False
    assert action.memory_influence["blocked_reason"] == "source_family_mismatch"


def test_exact_family_memory_can_change_scheduling():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={
            "task_family": "multi_source_conflict",
            "benchmark": "synthetic",
            "source_family": "multi_source_conflict",
        },
        avoid=[{"action": "writer_before_critic"}],
        confidence=0.95,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="multi_source_conflict", benchmark_name="synthetic")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write the final merged summary",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.agent_template == "critic"
    assert action.memory_influence["influence_type"] in {"changed_agent_selection", "changed_ordering"}
    assert action.memory_influence["eligible_to_influence"] is True
    assert action.memory_influence["trigger_match_score"] >= 0.7


def test_partial_match_support_only_cannot_change_agent():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        avoid=[{"action": "writer_before_critic"}],
        confidence=0.9,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="research_report", benchmark_name="synthetic")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write report summary",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.agent_template == "writer"
    assert action.memory_influence["influence_type"] == "support_only"
    assert action.memory_influence["eligible_to_influence"] is False
    assert 0.4 <= action.memory_influence["trigger_match_score"] < 0.7


def test_trigger_match_score_logged():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={
            "task_family": "research_report",
            "benchmark": "synthetic",
            "task_pattern": "write final draft",
            "constraints": ["requires_evidence", "verifier_required"],
        },
        recommended_schedule=["researcher", "writer", "critic"],
        confidence=0.92,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(
        objective="test",
        task_family="research_report",
        benchmark_name="synthetic",
        stakeholder_constraints={
            "task_pattern": "write final draft",
            "constraints": ["requires_evidence", "verifier_required"],
        },
    )
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write final draft",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    meta = action.memory_influence
    assert "trigger_match_score" in meta
    assert "eligible_to_influence" in meta
    assert "blocked_reason" in meta
    assert "current_task_family" in meta
    assert "memory_task_family" in meta
    assert meta["trigger_match_score"] >= 0.8


def test_shuffled_memory_blocked_on_family_mismatch():
    scheduler, store = _make_scheduler(use_memory=True)
    mem = ProceduralControlMemory(
        trigger={
            "task_family": "evidence_based_writing",
            "benchmark": "synthetic",
            "source_family": "debugging",
        },
        avoid=[{"action": "writer_before_evidence_complete"}],
        confidence=0.9,
    )
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test", task_family="evidence_based_writing", benchmark_name="synthetic")
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Write the answer quickly",
            state=TaskState.PENDING,
            priority=1.0,
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.agent_template == "writer"
    assert action.memory_influence["influence_type"] == "none"
    assert action.memory_influence["blocked_reason"] == "source_family_mismatch"


def test_replan_on_deadlock():
    scheduler, _ = _make_scheduler()
    wf = WorkflowSession(objective="test")
    # Task depends on a non-existent task → deadlock
    tasks = [
        TaskNode(
            workflow_id=wf.workflow_id,
            description="Blocked task",
            state=TaskState.PENDING,
            depends_on=["nonexistent-id"],
        ),
    ]
    action = scheduler.next_action(wf, tasks)
    assert action.action_type == "replan"
