"""Memory curator - extracts and maintains procedural control memory.

After each episode, the curator analyses the SchedulingEvaluation and
runs MemoryExtractionValidator before CREATE/UPDATE actions.
"""

from __future__ import annotations

from typing import Any, Optional

from .agent_registry import AgentRegistry
from .memory_extraction_validator import MemoryExtractionValidator
from .memory_store import MemoryStore
from .schemas import (
    CurationAction,
    DecisionEvent,
    MemoryStatus,
    ProceduralControlMemory,
    SchedulingEvaluation,
    WorkflowSession,
    _now,
    _uuid,
)


class MemoryCurator:
    """Analyses evaluations and curates procedural control memory."""

    def __init__(
        self,
        memory_store: MemoryStore,
        agent_registry: AgentRegistry | None = None,
        validator: MemoryExtractionValidator | None = None,
        confidence_positive_delta: float = 0.05,
        confidence_negative_delta: float = 0.10,
        confidence_negative_transfer_delta: float = 0.15,
        deprecate_threshold: float = 0.15,
    ) -> None:
        self._store = memory_store
        self._registry = agent_registry or AgentRegistry()
        self._validator = validator or MemoryExtractionValidator()
        self._pos_delta = confidence_positive_delta
        self._neg_delta = confidence_negative_delta
        self._neg_transfer_delta = confidence_negative_transfer_delta
        self._deprecate_threshold = deprecate_threshold

    def curate(
        self,
        workflow: WorkflowSession,
        evaluation: SchedulingEvaluation,
        decisions: list[DecisionEvent] | None = None,
    ) -> list[dict[str, Any]]:
        """Run curation logic and return action logs with reasons."""
        actions: list[dict[str, Any]] = []
        decisions = decisions or []

        # 1. Update existing memories that were used
        for mem_id in evaluation.useful_memory_refs:
            mem = self._store.get_procedural(mem_id)
            if not mem:
                continue

            candidate = mem.model_copy(deep=True)
            candidate.confidence = min(1.0, mem.confidence + self._pos_delta)
            candidate.supporting_episodes.append(workflow.workflow_id)
            candidate.last_updated = _now()

            validation = self._validator.validate(
                memory=candidate,
                workflow=workflow,
                evaluation=evaluation,
                decisions=decisions,
                registry=self._registry,
                prior_confidence=mem.confidence,
            )
            if validation["accepted"]:
                self._store.put_procedural(candidate)
                actions.append(
                    self._action(
                        action=CurationAction.UPDATE,
                        memory_id=mem_id,
                        reason="updated_from_useful_memory",
                        accepted=True,
                    )
                )
            else:
                actions.append(
                    self._action(
                        action=CurationAction.NEEDS_REVIEW,
                        memory_id=mem_id,
                        reason=f"validation_failed:{validation['reason']}",
                        accepted=False,
                    )
                )

        for mem_id in evaluation.harmful_memory_refs:
            mem = self._store.get_procedural(mem_id)
            if not mem:
                continue

            delta = self._neg_transfer_delta if evaluation.negative_transfer_detected else self._neg_delta
            candidate = mem.model_copy(deep=True)
            candidate.confidence = max(0.0, mem.confidence - delta)
            candidate.negative_cases.append(workflow.workflow_id)
            candidate.last_updated = _now()

            validation = self._validator.validate(
                memory=candidate,
                workflow=workflow,
                evaluation=evaluation,
                decisions=decisions,
                registry=self._registry,
                prior_confidence=mem.confidence,
            )
            if not validation["accepted"]:
                actions.append(
                    self._action(
                        action=CurationAction.NEEDS_REVIEW,
                        memory_id=mem_id,
                        reason=f"validation_failed:{validation['reason']}",
                        accepted=False,
                    )
                )
                continue

            if candidate.confidence < self._deprecate_threshold:
                candidate.status = MemoryStatus.DEPRECATED
                self._store.put_procedural(candidate)
                actions.append(
                    self._action(
                        action=CurationAction.DEPRECATE,
                        memory_id=mem_id,
                        reason="confidence_below_deprecate_threshold",
                        accepted=True,
                    )
                )
            else:
                self._store.put_procedural(candidate)
                actions.append(
                    self._action(
                        action=CurationAction.UPDATE,
                        memory_id=mem_id,
                        reason="updated_from_harmful_memory",
                        accepted=True,
                    )
                )

        # 2. Decide whether to create new memory
        schema_valid_rate = float(evaluation.scheduling_scores.get("agent_output_schema_valid_rate", 1.0))
        invalid_outputs_present = schema_valid_rate < 1.0

        should_create = (
            evaluation.benchmark_success
            and not invalid_outputs_present
            and (
                not evaluation.memory_used
                or self._is_novel_task_family(workflow.task_family)
            )
        )

        if should_create:
            candidate = self._create_memory_from_evaluation(workflow, evaluation)
            validation = self._validator.validate(
                memory=candidate,
                workflow=workflow,
                evaluation=evaluation,
                decisions=decisions,
                registry=self._registry,
                prior_confidence=None,
            )
            if validation["accepted"]:
                self._store.put_procedural(candidate)
                actions.append(
                    self._action(
                        action=CurationAction.CREATE,
                        memory_id=candidate.memory_id,
                        reason="created_from_successful_episode",
                        accepted=True,
                    )
                )
            else:
                actions.append(
                    self._action(
                        action=CurationAction.NEEDS_REVIEW,
                        memory_id="",
                        reason=f"validation_failed:{validation['reason']}",
                        accepted=False,
                    )
                )
        elif invalid_outputs_present and evaluation.benchmark_success:
            actions.append(
                self._action(
                    action=CurationAction.IGNORE,
                    memory_id="",
                    reason="invalid_agent_outputs_present",
                    accepted=False,
                )
            )
        elif not evaluation.benchmark_success and not evaluation.memory_used:
            actions.append(
                self._action(
                    action=CurationAction.IGNORE,
                    memory_id="",
                    reason="failed_without_memory_signal",
                    accepted=False,
                )
            )

        return actions

    def _create_memory_from_evaluation(
        self,
        workflow: WorkflowSession,
        evaluation: SchedulingEvaluation,
    ) -> ProceduralControlMemory:
        """Create a new procedural memory entry from a successful episode."""
        scores = evaluation.scheduling_scores
        recommended_schedule: list[str] = []
        if scores.get("agent_assignment_quality", 0) > 0.7:
            recommended_schedule = ["planner", "researcher", "writer", "critic"]

        trigger: dict[str, Any] = {
            "task_family": workflow.task_family,
            "benchmark": workflow.benchmark_name,
        }

        avoid: list[dict[str, str]] = []
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

    @staticmethod
    def _action(
        action: CurationAction,
        memory_id: str,
        reason: str,
        accepted: bool,
    ) -> dict[str, Any]:
        return {
            "action": action,
            "memory_id": memory_id,
            "reason": reason,
            "accepted": accepted,
        }
