"""Shared blackboard / artifact store.

Data-plane component: agents write evidence, drafts, critiques, and final
outputs here.  The orchestrator reads them to inform scheduling.
"""

from __future__ import annotations

from typing import Optional

from .schemas import Artifact, ArtifactStatus, _now, _uuid


class Blackboard:
    """In-memory artifact store keyed by artifact_id."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    def write(
        self,
        workflow_id: str,
        artifact_type: str,
        content: object,
        created_by: str,
        metadata: dict | None = None,
        artifact_id: str | None = None,
    ) -> Artifact:
        """Create or update an artifact on the blackboard."""
        aid = artifact_id or _uuid()
        existing = self._artifacts.get(aid)
        version = (existing.version + 1) if existing else 1

        artifact = Artifact(
            artifact_id=aid,
            workflow_id=workflow_id,
            artifact_type=artifact_type,
            content=content,
            created_by=created_by,
            created_at=_now(),
            version=version,
            status=ArtifactStatus.DRAFT,
            metadata=metadata or {},
        )
        self._artifacts[aid] = artifact
        return artifact

    def read(self, artifact_id: str) -> Optional[Artifact]:
        return self._artifacts.get(artifact_id)

    def list_artifacts(
        self,
        workflow_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
    ) -> list[Artifact]:
        arts = list(self._artifacts.values())
        if workflow_id:
            arts = [a for a in arts if a.workflow_id == workflow_id]
        if artifact_type:
            arts = [a for a in arts if a.artifact_type == artifact_type]
        return arts

    def finalize(self, artifact_id: str) -> Optional[Artifact]:
        """Mark an artifact as final."""
        art = self._artifacts.get(artifact_id)
        if art:
            art.status = ArtifactStatus.FINAL
        return art

    def clear(self) -> None:
        self._artifacts.clear()
