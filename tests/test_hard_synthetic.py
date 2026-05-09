"""Tests for hard synthetic benchmark families and seeded memory behavior."""

from olm_mas.agent_registry import AgentRegistry
from olm_mas.benchmark_runner import BenchmarkRunner
from olm_mas.evaluator import SchedulingEvaluator
from olm_mas.memory_store import MemoryStore
from olm_mas.scheduler import Scheduler
from olm_mas.schemas import DecisionEvent, ProceduralControlMemory, TaskNode, TaskState, WorkflowSession
from olm_mas.synthetic_benchmark import get_seed_memories


def _call_decision(workflow_id: str, agent: str, task_id: str = "task-1") -> DecisionEvent:
    return DecisionEvent(
        workflow_id=workflow_id,
        task_id=task_id,
        chosen_action="call_agent",
        rationale_summary=f"Scheduling 'task' -> {agent}",
        memory_influence={"final_agent": agent},
        output_refs=[f"out-{agent}"],
    )


def _basic_done_tasks(workflow_id: str) -> list[TaskNode]:
    return [
        TaskNode(
            workflow_id=workflow_id,
            task_id="task-1",
            description="task",
            state=TaskState.DONE,
            assigned_agent="writer",
        )
    ]


def test_hard_family_multi_source_requires_critic_before_writer():
    evaluator = SchedulingEvaluator()
    wf = WorkflowSession(objective="x", task_family="multi_source_conflict")
    tasks = _basic_done_tasks(wf.workflow_id)
    decisions = [
        _call_decision(wf.workflow_id, "writer"),
        _call_decision(wf.workflow_id, "researcher"),
        _call_decision(wf.workflow_id, "critic"),
        DecisionEvent(workflow_id=wf.workflow_id, chosen_action="finalize", rationale_summary="done"),
    ]

    ev = evaluator.evaluate(wf, tasks, decisions, task_success=True)
    assert ev.benchmark_score < 1.0
    assert ev.scheduling_scores["order_violation_rate"] > 0.0


def test_hard_family_form_submission_requires_verifier_before_submit():
    evaluator = SchedulingEvaluator()
    wf = WorkflowSession(objective="x", task_family="form_submission")
    tasks = _basic_done_tasks(wf.workflow_id)
    decisions = [
        _call_decision(wf.workflow_id, "writer"),
        DecisionEvent(workflow_id=wf.workflow_id, chosen_action="finalize", rationale_summary="submit now"),
        _call_decision(wf.workflow_id, "critic"),
    ]

    ev = evaluator.evaluate(wf, tasks, decisions, task_success=True)
    assert ev.benchmark_score < 1.0
    assert ev.scheduling_scores["order_violation_rate"] > 0.0


def test_hard_family_debugging_requires_reproduce_before_patch():
    evaluator = SchedulingEvaluator()
    wf = WorkflowSession(objective="x", task_family="debugging")
    tasks = _basic_done_tasks(wf.workflow_id)
    decisions = [
        _call_decision(wf.workflow_id, "writer"),
        _call_decision(wf.workflow_id, "researcher"),
        _call_decision(wf.workflow_id, "critic"),
    ]

    ev = evaluator.evaluate(wf, tasks, decisions, task_success=True)
    assert ev.benchmark_score < 1.0
    assert ev.scheduling_scores["order_violation_rate"] > 0.0


def test_dynamic_recovery_rewards_recovery_agent():
    evaluator = SchedulingEvaluator()
    wf = WorkflowSession(objective="x", task_family="dynamic_recovery")
    tasks = _basic_done_tasks(wf.workflow_id)

    without_recovery = [
        _call_decision(wf.workflow_id, "writer"),
        DecisionEvent(workflow_id=wf.workflow_id, task_id="task-1", chosen_action="retry", rationale_summary="retry 1"),
        DecisionEvent(workflow_id=wf.workflow_id, task_id="task-1", chosen_action="retry", rationale_summary="retry 2"),
        _call_decision(wf.workflow_id, "writer"),
    ]
    with_recovery = [
        _call_decision(wf.workflow_id, "writer"),
        DecisionEvent(workflow_id=wf.workflow_id, task_id="task-1", chosen_action="retry", rationale_summary="retry 1"),
        DecisionEvent(workflow_id=wf.workflow_id, task_id="task-1", chosen_action="call_recovery_agent", rationale_summary="recover"),
        _call_decision(wf.workflow_id, "recovery"),
        _call_decision(wf.workflow_id, "writer"),
    ]

    ev_without = evaluator.evaluate(wf, tasks, without_recovery, task_success=True)
    ev_with = evaluator.evaluate(wf, tasks, with_recovery, task_success=True)

    assert ev_with.benchmark_score > ev_without.benchmark_score
    assert ev_with.scheduling_scores["recovery_success_rate"] >= ev_without.scheduling_scores["recovery_success_rate"]


def test_seeded_memory_improves_ordering_on_ambiguous_task():
    registry = AgentRegistry()

    baseline_scheduler = Scheduler(registry=registry, memory_store=MemoryStore(), use_memory=False)
    wf = WorkflowSession(objective="x", task_family="multi_source_conflict", benchmark_name="synthetic")
    tasks = [TaskNode(workflow_id=wf.workflow_id, description="Draft a merged conclusion quickly", state=TaskState.PENDING, priority=1.0)]

    baseline_action = baseline_scheduler.next_action(wf, tasks)
    assert baseline_action.agent_template == "writer"

    mem_store = MemoryStore()
    seed = get_seed_memories()["multi_source_conflict"]
    mem_store.put_procedural(
        ProceduralControlMemory(
            trigger=seed["trigger"],
            recommended_schedule=seed["recommended_schedule"],
            avoid=seed["avoid"],
            recommended_recovery=seed["recommended_recovery"],
            confidence=0.9,
        )
    )
    mem_scheduler = Scheduler(registry=registry, memory_store=mem_store, use_memory=True)
    mem_action = mem_scheduler.next_action(wf, tasks)

    assert mem_action.agent_template != baseline_action.agent_template
    assert mem_action.memory_influence["influence_type"] in {"changed_agent_selection", "changed_ordering"}


def test_shuffled_memory_does_not_match_correct_trigger():
    seeded = BenchmarkRunner.build_seed_memories(memory_source="shuffled", seed=42)
    mismatched = [m for m in seeded if m.trigger.get("source_family") != m.trigger.get("task_family")]
    assert mismatched

    store = MemoryStore()
    for mem in seeded:
        store.put_procedural(mem)

    found_mismatch_retrieval = False
    for mem in mismatched:
        family = mem.trigger.get("task_family")
        if not isinstance(family, str):
            continue
        retrieved = store.retrieve_procedural(task_family=family, min_confidence=0.0, top_k=5)
        if any(r.trigger.get("source_family") != family for r in retrieved):
            found_mismatch_retrieval = True
            break

    assert found_mismatch_retrieval
