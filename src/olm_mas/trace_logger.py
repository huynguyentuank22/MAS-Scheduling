"""Append-only JSONL trace logger.

Every DecisionEvent and ExecutionTraceEvent is serialised to a JSONL file
scoped by workflow_id.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .schemas import DecisionEvent, ExecutionTraceEvent


class TraceLogger:
    """Writes trace events to JSONL files."""

    def __init__(self, trace_dir: str = "storage/traces") -> None:
        self._trace_dir = trace_dir
        os.makedirs(self._trace_dir, exist_ok=True)

    def _path(self, workflow_id: str) -> Path:
        return Path(self._trace_dir) / f"{workflow_id}.jsonl"

    def _append(self, workflow_id: str, record: dict) -> None:
        path = self._path(workflow_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def log_decision(self, event: DecisionEvent) -> None:
        record = {"_type": "DecisionEvent", **event.model_dump()}
        self._append(event.workflow_id, record)

    def log_trace(self, event: ExecutionTraceEvent) -> None:
        record = {"_type": "ExecutionTraceEvent", **event.model_dump()}
        self._append(event.workflow_id, record)

    def read_trace(self, workflow_id: str) -> list[dict]:
        path = self._path(workflow_id)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        return [json.loads(line) for line in lines if line.strip()]
