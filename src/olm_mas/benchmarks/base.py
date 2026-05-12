"""Base interface for benchmark adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BenchmarkAdapter(ABC):
    """Adapter interface for external benchmarks."""

    @abstractmethod
    def load_tasks(self, split: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Load tasks for a benchmark split."""

    @abstractmethod
    def get_task_prompt(self, task: dict[str, Any]) -> str:
        """Return the prompt text for a task."""

    @abstractmethod
    def get_task_metadata(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return normalized metadata for scheduling/memory triggers."""

    @abstractmethod
    def provide_tools(self) -> list[str]:
        """Return benchmark-relevant tool names."""

    @abstractmethod
    def evaluate(
        self,
        task: dict[str, Any],
        final_output: Any,
        artifacts: list[Any],
    ) -> dict[str, Any]:
        """Evaluate final output and artifacts for one task."""
