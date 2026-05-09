"""In-memory store for all OLM-MAS entities.

Supports typed CRUD, procedural memory retrieval with confidence filtering
and trigger matching.  Optionally serialises to JSON files for persistence.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .schemas import (
    DecisionEvent,
    EpisodeReflection,
    MemoryStatus,
    ProceduralControlMemory,
    SchedulingEvaluation,
    TaskNode,
    WorkflowSession,
)


class MemoryStore:
    """Dict-backed entity store with optional JSON persistence."""

    def __init__(self, memory_dir: Optional[str] = None) -> None:
        # Entity tables keyed by primary ID
        self._workflows: dict[str, WorkflowSession] = {}
        self._tasks: dict[str, TaskNode] = {}
        self._decisions: dict[str, DecisionEvent] = {}
        self._evaluations: dict[str, SchedulingEvaluation] = {}
        self._reflections: dict[str, EpisodeReflection] = {}
        self._procedural: dict[str, ProceduralControlMemory] = {}
        self._memory_dir = memory_dir

    # ---- Workflow ----------------------------------------------------------

    def put_workflow(self, wf: WorkflowSession) -> None:
        self._workflows[wf.workflow_id] = wf

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowSession]:
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> list[WorkflowSession]:
        return list(self._workflows.values())

    # ---- Task --------------------------------------------------------------

    def put_task(self, task: TaskNode) -> None:
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[TaskNode]:
        return self._tasks.get(task_id)

    def list_tasks(self, workflow_id: Optional[str] = None) -> list[TaskNode]:
        tasks = list(self._tasks.values())
        if workflow_id:
            tasks = [t for t in tasks if t.workflow_id == workflow_id]
        return tasks

    # ---- Decision events ---------------------------------------------------

    def put_decision(self, event: DecisionEvent) -> None:
        self._decisions[event.decision_id] = event

    def list_decisions(self, workflow_id: Optional[str] = None) -> list[DecisionEvent]:
        events = list(self._decisions.values())
        if workflow_id:
            events = [e for e in events if e.workflow_id == workflow_id]
        return events

    # ---- Scheduling evaluations --------------------------------------------

    def put_evaluation(self, ev: SchedulingEvaluation) -> None:
        self._evaluations[ev.evaluation_id] = ev

    def list_evaluations(self, workflow_id: Optional[str] = None) -> list[SchedulingEvaluation]:
        evals = list(self._evaluations.values())
        if workflow_id:
            evals = [e for e in evals if e.workflow_id == workflow_id]
        return evals

    # ---- Episode reflections ----------------------------------------------

    def put_reflection(self, reflection: EpisodeReflection) -> None:
        self._reflections[reflection.episode_id] = reflection

    def get_reflection(self, episode_id: str) -> Optional[EpisodeReflection]:
        return self._reflections.get(episode_id)

    def list_reflections(self, workflow_id: Optional[str] = None) -> list[EpisodeReflection]:
        reflections = list(self._reflections.values())
        if workflow_id:
            reflections = [r for r in reflections if r.workflow_id == workflow_id]
        return reflections

    # ---- Procedural control memory -----------------------------------------

    def put_procedural(self, mem: ProceduralControlMemory) -> None:
        self._procedural[mem.memory_id] = mem
        self._persist_procedural(mem)

    def get_procedural(self, memory_id: str) -> Optional[ProceduralControlMemory]:
        return self._procedural.get(memory_id)

    def list_procedural(self, status: Optional[MemoryStatus] = None) -> list[ProceduralControlMemory]:
        mems = list(self._procedural.values())
        if status:
            mems = [m for m in mems if m.status == status]
        return mems

    def retrieve_procedural(
        self,
        task_family: Optional[str] = None,
        tags: Optional[list[str]] = None,
        min_confidence: float = 0.0,
        top_k: int = 3,
    ) -> list[ProceduralControlMemory]:
        """Retrieve procedural memories matching trigger criteria.

        Simple keyword matching on trigger fields for MVP.
        """
        candidates: list[ProceduralControlMemory] = []
        for mem in self._procedural.values():
            if mem.status != MemoryStatus.ACTIVE:
                continue
            if mem.confidence < min_confidence:
                continue
            # Simple trigger matching
            trigger = mem.trigger
            if task_family and trigger.get("task_family") and trigger["task_family"] != task_family:
                continue
            if tags and trigger.get("tags"):
                if not set(trigger["tags"]).intersection(set(tags)):
                    continue
            candidates.append(mem)

        # Sort by confidence descending
        candidates.sort(key=lambda m: m.confidence, reverse=True)
        return candidates[:top_k]

    def delete_procedural(self, memory_id: str) -> bool:
        return self._procedural.pop(memory_id, None) is not None

    def clear_all(self) -> None:
        """Reset all tables — useful for tests."""
        self._workflows.clear()
        self._tasks.clear()
        self._decisions.clear()
        self._evaluations.clear()
        self._reflections.clear()
        self._procedural.clear()

    # ---- Persistence helpers -----------------------------------------------

    def _persist_procedural(self, mem: ProceduralControlMemory) -> None:
        if not self._memory_dir:
            return
        os.makedirs(self._memory_dir, exist_ok=True)
        path = Path(self._memory_dir) / f"{mem.memory_id}.json"
        path.write_text(mem.model_dump_json(indent=2), encoding="utf-8")

    def load_procedural_from_disk(self) -> int:
        """Load procedural memories from JSON files. Returns count loaded."""
        if not self._memory_dir or not os.path.isdir(self._memory_dir):
            return 0
        count = 0
        for fname in os.listdir(self._memory_dir):
            if not fname.endswith(".json"):
                continue
            path = Path(self._memory_dir) / fname
            data = json.loads(path.read_text(encoding="utf-8"))
            mem = ProceduralControlMemory(**data)
            self._procedural[mem.memory_id] = mem
            count += 1
        return count
