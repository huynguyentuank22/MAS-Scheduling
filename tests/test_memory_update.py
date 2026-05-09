"""Tests for memory curation — CREATE, UPDATE, DEPRECATE logic."""

from olm_mas.memory_curator import MemoryCurator
from olm_mas.memory_store import MemoryStore
from olm_mas.schemas import (
    CurationAction,
    MemoryStatus,
    ProceduralControlMemory,
    SchedulingEvaluation,
    WorkflowSession,
)


def _make_curator() -> tuple[MemoryCurator, MemoryStore]:
    store = MemoryStore()
    curator = MemoryCurator(
        memory_store=store,
        confidence_positive_delta=0.05,
        confidence_negative_delta=0.10,
        confidence_negative_transfer_delta=0.15,
        deprecate_threshold=0.15,
    )
    return curator, store


def test_create_new_memory_on_success():
    curator, store = _make_curator()
    wf = WorkflowSession(objective="test", task_family="research_report")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=True,
        benchmark_score=1.0,
        scheduling_scores={"agent_assignment_quality": 0.9},
    )

    actions = curator.curate(wf, ev)
    assert len(actions) == 1
    assert actions[0][0] == CurationAction.CREATE
    # Memory should now exist in the store
    mems = store.list_procedural()
    assert len(mems) == 1
    assert mems[0].trigger.get("task_family") == "research_report"


def test_update_useful_memory():
    curator, store = _make_curator()
    mem = ProceduralControlMemory(confidence=0.5)
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=True,
        useful_memory_refs=[mem.memory_id],
        memory_used=[mem.memory_id],
    )

    actions = curator.curate(wf, ev)
    assert any(a == CurationAction.UPDATE for a, _ in actions)

    # Confidence should have increased
    updated = store.get_procedural(mem.memory_id)
    assert updated is not None
    assert updated.confidence == 0.55  # 0.5 + 0.05


def test_deprecate_harmful_memory():
    curator, store = _make_curator()
    mem = ProceduralControlMemory(confidence=0.20)
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=False,
        harmful_memory_refs=[mem.memory_id],
        memory_used=[mem.memory_id],
        negative_transfer_detected=True,
    )

    actions = curator.curate(wf, ev)
    # Should deprecate because 0.20 - 0.15 = 0.05 < 0.15 threshold
    assert any(a == CurationAction.DEPRECATE for a, _ in actions)

    updated = store.get_procedural(mem.memory_id)
    assert updated is not None
    assert updated.status == MemoryStatus.DEPRECATED


def test_update_harmful_above_threshold():
    curator, store = _make_curator()
    mem = ProceduralControlMemory(confidence=0.60)
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=False,
        harmful_memory_refs=[mem.memory_id],
        memory_used=[mem.memory_id],
        negative_transfer_detected=False,
    )

    actions = curator.curate(wf, ev)
    # 0.60 - 0.10 = 0.50 > 0.15 → UPDATE, not DEPRECATE
    assert any(a == CurationAction.UPDATE for a, _ in actions)

    updated = store.get_procedural(mem.memory_id)
    assert updated is not None
    assert updated.confidence == 0.50
    assert updated.status == MemoryStatus.ACTIVE


def test_ignore_on_failure_no_memory():
    curator, store = _make_curator()
    wf = WorkflowSession(objective="test")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=False,
    )

    actions = curator.curate(wf, ev)
    assert any(a == CurationAction.IGNORE for a, _ in actions)


def test_supporting_episodes_tracked():
    curator, store = _make_curator()
    mem = ProceduralControlMemory(confidence=0.5)
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=True,
        useful_memory_refs=[mem.memory_id],
        memory_used=[mem.memory_id],
    )

    curator.curate(wf, ev)
    updated = store.get_procedural(mem.memory_id)
    assert updated is not None
    assert wf.workflow_id in updated.supporting_episodes


def test_negative_cases_tracked():
    curator, store = _make_curator()
    mem = ProceduralControlMemory(confidence=0.8)
    store.put_procedural(mem)

    wf = WorkflowSession(objective="test")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=False,
        harmful_memory_refs=[mem.memory_id],
        memory_used=[mem.memory_id],
    )

    curator.curate(wf, ev)
    updated = store.get_procedural(mem.memory_id)
    assert updated is not None
    assert wf.workflow_id in updated.negative_cases


def test_curator_creates_for_novel_family():
    curator, store = _make_curator()
    existing = ProceduralControlMemory(
        trigger={"task_family": "research_report"},
        confidence=0.7,
    )
    store.put_procedural(existing)

    wf = WorkflowSession(objective="test", task_family="data_analysis")
    ev = SchedulingEvaluation(
        workflow_id=wf.workflow_id,
        benchmark_success=True,
        benchmark_score=1.0,
        scheduling_scores={"agent_assignment_quality": 0.9},
        memory_used=[existing.memory_id],
        useful_memory_refs=[existing.memory_id],
    )

    actions = curator.curate(wf, ev)
    assert any(a == CurationAction.CREATE for a, _ in actions)

    mems = store.list_procedural()
    assert any(m.trigger.get("task_family") == "data_analysis" for m in mems)
