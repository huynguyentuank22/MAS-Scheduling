"""Tests for MemoryStore — CRUD, retrieval, and confidence filtering."""

from olm_mas.memory_store import MemoryStore
from olm_mas.schemas import (
    DecisionEvent,
    MemoryStatus,
    ProceduralControlMemory,
    TaskNode,
    WorkflowSession,
)


def _make_store() -> MemoryStore:
    return MemoryStore()


def test_workflow_crud():
    store = _make_store()
    wf = WorkflowSession(objective="test")
    store.put_workflow(wf)
    assert store.get_workflow(wf.workflow_id) is wf
    assert len(store.list_workflows()) == 1


def test_task_crud():
    store = _make_store()
    task = TaskNode(workflow_id="wf-1", description="task 1")
    store.put_task(task)
    assert store.get_task(task.task_id) is task
    assert len(store.list_tasks(workflow_id="wf-1")) == 1
    assert len(store.list_tasks(workflow_id="wf-2")) == 0


def test_decision_crud():
    store = _make_store()
    d = DecisionEvent(workflow_id="wf-1", chosen_action="call_agent")
    store.put_decision(d)
    assert len(store.list_decisions(workflow_id="wf-1")) == 1


def test_procedural_crud():
    store = _make_store()
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        confidence=0.7,
    )
    store.put_procedural(mem)
    assert store.get_procedural(mem.memory_id) is mem
    assert len(store.list_procedural()) == 1


def test_procedural_retrieval_by_task_family():
    store = _make_store()
    mem1 = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        confidence=0.8,
    )
    mem2 = ProceduralControlMemory(
        trigger={"task_family": "data_analysis"},
        confidence=0.6,
    )
    store.put_procedural(mem1)
    store.put_procedural(mem2)

    results = store.retrieve_procedural(task_family="research_report")
    assert len(results) == 1
    assert results[0].memory_id == mem1.memory_id


def test_procedural_retrieval_confidence_filter():
    store = _make_store()
    mem_low = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        confidence=0.2,
    )
    mem_high = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        confidence=0.8,
    )
    store.put_procedural(mem_low)
    store.put_procedural(mem_high)

    results = store.retrieve_procedural(
        task_family="research_report",
        min_confidence=0.5,
    )
    assert len(results) == 1
    assert results[0].memory_id == mem_high.memory_id


def test_procedural_retrieval_top_k():
    store = _make_store()
    for i in range(10):
        mem = ProceduralControlMemory(
            trigger={"task_family": "research_report"},
            confidence=0.5 + i * 0.03,
        )
        store.put_procedural(mem)

    results = store.retrieve_procedural(
        task_family="research_report",
        top_k=3,
    )
    assert len(results) == 3
    # Should be sorted by confidence descending
    assert results[0].confidence >= results[1].confidence >= results[2].confidence


def test_deprecated_memories_excluded():
    store = _make_store()
    mem = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        confidence=0.9,
        status=MemoryStatus.DEPRECATED,
    )
    store.put_procedural(mem)
    results = store.retrieve_procedural(task_family="research_report")
    assert len(results) == 0


def test_clear_all():
    store = _make_store()
    store.put_workflow(WorkflowSession(objective="test"))
    store.put_task(TaskNode(workflow_id="wf-1", description="t"))
    store.clear_all()
    assert len(store.list_workflows()) == 0
    assert len(store.list_tasks()) == 0


def test_delete_procedural():
    store = _make_store()
    mem = ProceduralControlMemory(confidence=0.5)
    store.put_procedural(mem)
    assert store.delete_procedural(mem.memory_id) is True
    assert store.get_procedural(mem.memory_id) is None
    assert store.delete_procedural("nonexistent") is False
