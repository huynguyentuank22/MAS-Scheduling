"""GAIA-lite benchmark adapter (local JSONL sample-compatible)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BenchmarkAdapter


_DEFAULT_TOOLS = [
    "search",
    "calculator",
    "file_reader",
    "web_browser",
]


def get_gaia_lite_seed_memories() -> dict[str, dict[str, Any]]:
    """Seeded procedural memories for GAIA-lite families."""
    return {
        "numeric_reasoning": {
            "trigger": {"benchmark": "gaia_lite", "task_family": "numeric_reasoning"},
            "recommended_schedule": ["planner", "tool_executor", "calculator", "verifier"],
            "avoid": [{"action": "writer_before_evidence_complete"}],
            "recommended_recovery": [],
            "confidence": 0.82,
        },
        "web_research": {
            "trigger": {"benchmark": "gaia_lite", "task_family": "web_research"},
            "recommended_schedule": ["planner", "researcher", "writer", "verifier"],
            "avoid": [{"action": "writer_before_evidence_complete"}],
            "recommended_recovery": [],
            "confidence": 0.81,
        },
        "multi_hop": {
            "trigger": {"benchmark": "gaia_lite", "task_family": "multi_hop"},
            "recommended_schedule": ["planner", "researcher", "critic", "writer", "verifier"],
            "avoid": [{"action": "writer_before_critic"}],
            "recommended_recovery": [],
            "confidence": 0.84,
        },
        "file_question": {
            "trigger": {"benchmark": "gaia_lite", "task_family": "file_question"},
            "recommended_schedule": ["planner", "file_reader", "writer", "verifier"],
            "avoid": [{"action": "finalize_without_verifier"}],
            "recommended_recovery": [],
            "confidence": 0.8,
        },
        "verification_heavy": {
            "trigger": {"benchmark": "gaia_lite", "task_family": "verification_heavy"},
            "recommended_schedule": ["planner", "researcher", "critic", "verifier", "writer"],
            "avoid": [{"action": "finalize_without_verifier"}],
            "recommended_recovery": [],
            "confidence": 0.83,
        },
    }


class GAIALiteAdapter(BenchmarkAdapter):
    """Local GAIA-lite adapter backed by JSONL tasks."""

    def __init__(self, data_path: str | Path | None = None) -> None:
        if data_path is None:
            data_path = Path("data/gaia_lite_sample.jsonl")
        self._data_path = Path(data_path)
        self._loaded_tasks: list[dict[str, Any]] = []

    def load_tasks(self, split: str, limit: int | None = None) -> list[dict[str, Any]]:
        if split != "sample":
            alt = self._data_path.with_name(f"gaia_lite_{split}.jsonl")
            path = alt if alt.exists() else self._data_path
        else:
            path = self._data_path

        if not path.exists():
            raise FileNotFoundError(f"GAIA-lite task file not found: {path}")

        tasks: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            task = json.loads(line)
            tasks.append(task)

        if limit is not None:
            tasks = tasks[: max(limit, 0)]
        self._loaded_tasks = tasks
        return tasks

    def get_task_prompt(self, task: dict[str, Any]) -> str:
        return str(task.get("question") or "")

    def get_task_metadata(self, task: dict[str, Any]) -> dict[str, Any]:
        constraints = task.get("constraints") or {}
        if not isinstance(constraints, dict):
            constraints = {"raw_constraints": constraints}
        return {
            "benchmark": "gaia_lite",
            "task_id": str(task.get("task_id") or ""),
            "task_family": str(task.get("task_family") or "unknown"),
            "task_pattern": str(task.get("task_pattern") or ""),
            "constraints": constraints,
            "required_tools": list(task.get("required_tools") or []),
        }

    def provide_tools(self) -> list[str]:
        tools: set[str] = set(_DEFAULT_TOOLS)
        for task in self._loaded_tasks:
            for tool in task.get("required_tools") or []:
                if isinstance(tool, str) and tool.strip():
                    tools.add(tool.strip())
        return sorted(tools)

    def evaluate(
        self,
        task: dict[str, Any],
        final_output: Any,
        artifacts: list[Any],
    ) -> dict[str, Any]:
        expected = task.get("expected_answer")
        output_text = self._stringify_output(final_output)
        output_norm = output_text.strip().lower()

        if expected is None:
            success = bool(output_norm)
            score = 1.0 if success else 0.0
            reason = "non_empty_output" if success else "empty_output"
        else:
            expected_norm = str(expected).strip().lower()
            success = expected_norm in output_norm
            score = 1.0 if success else 0.0
            reason = "contains_expected_answer" if success else "missing_expected_answer"

        return {
            "success": bool(success),
            "score": float(score),
            "reason": reason,
            "artifact_count": len(artifacts),
            "has_expected_answer": expected is not None,
        }

    @staticmethod
    def _stringify_output(final_output: Any) -> str:
        if final_output is None:
            return ""
        if isinstance(final_output, str):
            return final_output
        if isinstance(final_output, (int, float, bool)):
            return str(final_output)
        if isinstance(final_output, dict):
            return json.dumps(final_output, ensure_ascii=True, sort_keys=True)
        if isinstance(final_output, list):
            return json.dumps(final_output, ensure_ascii=True)
        return str(final_output)
