"""Memory curator - extracts and maintains procedural control memory.

After each episode, the curator analyses the SchedulingEvaluation and
decides whether to CREATE, UPDATE, IGNORE, or DEPRECATE procedural
control memories.
"""

from __future__ import annotations

from typing import Optional

from .schemas import (
    CurationAction,
    MemoryStatus,
    ProceduralControlMemory,
    SchedulingEvaluation,
    WorkflowSession,
    _now,
    _uuid,
)
from .memory_store import MemoryStore


class MemoryCurator:
    """Analyses evaluations and curates procedural control memory."""

    def __init__(
        self,
        memory_store: MemoryStore,
        confidence_positive_delta: float = 0.05,
        confidence_negative_delta: float = 0.10,
        confidence_negative_transfer_delta: float = 0.15,
        deprecate_threshold: float = 0.15,
    ) -> None:
        self._store = memory_store
        self._pos_delta = confidence_positive_delta
        self._neg_delta = confidence_negative_delta
        self._neg_transfer_delta = confidence_negative_transfer_delta
        self._deprecate_threshold = deprecate_threshold

    def curate(
        self,
        workflow: WorkflowSession,
        evaluation: SchedulingEvaluation,
    ) -> list[tuple[CurationAction, str]]:
        """Run curation logic. Returns list of (action, memory_id) pairs."""
        actions: list[tuple[CurationAction, str]] = []

        # 1. Update existing memories that were used
        for mem_id in evaluation.useful_memory_refs:
            mem = self._store.get_procedural(mem_id)
            if mem:
                mem.confidence = min(1.0, mem.confidence + self._pos_delta)
                mem.supporting_episodes.append(workflow.workflow_id)
                mem.last_updated = _now()
                self._store.put_procedural(mem)
                actions.append((CurationAction.UPDATE, mem_id))

        for mem_id in evaluation.harmful_memory_refs:
            mem = self._store.get_procedural(mem_id)
            if mem:
                delta = self._neg_transfer_delta if evaluation.negative_transfer_detected else self._neg_delta
                mem.confidence = max(0.0, mem.confidence - delta)
                mem.negative_cases.append(workflow.workflow_id)
                mem.last_updated = _now()
                if mem.confidence < self._deprecate_threshold:
                    mem.status = MemoryStatus.DEPRECATED
                    actions.append((CurationAction.DEPRECATE, mem_id))
                else:
                    actions.append((CurationAction.UPDATE, mem_id))
                self._store.put_procedural(mem)

        # 2. Decide whether to create new memory
        should_create = (
            evaluation.benchmark_success and (
                not evaluation.memory_used
                or self._is_novel_task_family(workflow.task_family)
            )
        )
        if should_create:
            # Successful episode with no memory used or novel family signal.
            new_mem = self._create_memory_from_evaluation(workflow, evaluation)
            self._store.put_procedural(new_mem)
            actions.append((CurationAction.CREATE, new_mem.memory_id))
        elif not evaluation.benchmark_success and not evaluation.memory_used:
            # Failed with no memory - nothing to learn yet (IGNORE)
            actions.append((CurationAction.IGNORE, ""))

        return actions

    def _create_memory_from_evaluation(
        self,
        workflow: WorkflowSession,
        evaluation: SchedulingEvaluation,
    ) -> ProceduralControlMemory:
        """Create a new procedural memory entry from a successful episode."""
        # Extract the schedule that worked
        scores = evaluation.scheduling_scores
        recommended_schedule: list[str] = []
        if scores.get("agent_assignment_quality", 0) > 0.7:
            recommended_schedule = ["planner", "researcher", "writer", "critic"]

        trigger: dict = {
            "task_family": workflow.task_family,
            "benchmark": workflow.benchmark_name,
        }

        avoid: list[dict] = []
        for factor in evaluation.failure_factors:
            avoid.append({"action": factor, "reason": "observed failure"})

        return ProceduralControlMemory(
            memory_id=_uuid(),
            trigger=trigger,
            recommended_schedule=recommended_schedule,
            avoid=avoid,
            confidence=0.5,
            supporting_episodes=[workflow.workflow_id],
            last_updated=_now(),
            status=MemoryStatus.ACTIVE,
        )

    def _is_novel_task_family(self, task_family: Optional[str]) -> bool:
        """Return True when no active memory exists for the task family."""
        if not task_family:
            return True
        for mem in self._store.list_procedural(status=MemoryStatus.ACTIVE):
            if mem.trigger.get("task_family") == task_family:
                return False
        return True
