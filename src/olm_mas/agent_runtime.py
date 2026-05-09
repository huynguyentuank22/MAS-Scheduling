"""Mock agent runtime.

Each agent type produces structured output simulating real agent behaviour.
Quality and latency are simulated with seeded randomness for reproducibility.
"""

from __future__ import annotations

import random
import time
from typing import Any

from .schemas import AgentProfile, Artifact, _now, _uuid


# ---------------------------------------------------------------------------
# Mock output templates per agent type
# ---------------------------------------------------------------------------

_MOCK_OUTPUTS: dict[str, dict[str, Any]] = {
    "planner": {
        "artifact_type": "plan",
        "template": {
            "steps": [
                {"step": 1, "action": "research", "description": "Gather evidence"},
                {"step": 2, "action": "draft", "description": "Write initial draft"},
                {"step": 3, "action": "verify", "description": "Verify draft quality"},
            ],
        },
    },
    "researcher": {
        "artifact_type": "evidence",
        "template": {
            "findings": ["Finding A: relevant data identified"],
            "confidence": 0.75,
            "sources": ["source_1"],
        },
    },
    "writer": {
        "artifact_type": "draft",
        "template": {
            "draft_text": "Draft output based on evidence and task context.",
            "word_count": 150,
        },
    },
    "critic": {
        "artifact_type": "critique",
        "template": {
            "issues": [],
            "pass": True,
            "score": 0.85,
        },
    },
    "recovery": {
        "artifact_type": "recovery_plan",
        "template": {
            "diagnosis": "Identified root cause of failure.",
            "recommended_action": "retry",
            "retry_with_changes": ["increase context window"],
        },
    },
}


class AgentRuntime:
    """Simulates agent execution and returns structured output."""

    def __init__(self, seed: int = 42, failure_rate: float = 0.10) -> None:
        self._rng = random.Random(seed)
        self._failure_rate = failure_rate

    def run(
        self,
        profile: AgentProfile,
        task_description: str,
        context: dict[str, Any] | None = None,
        quality_boost: float = 0.0,
    ) -> dict[str, Any]:
        """Run a mock agent and return a result dict.

        Returns:
            dict with keys: success, artifact_type, content, latency_sec
        """
        agent_type = profile.agent_type
        mock = _MOCK_OUTPUTS.get(agent_type, {
            "artifact_type": "generic",
            "template": {"output": "generic output"},
        })

        # Simulate failure
        if self._rng.random() < self._failure_rate:
            return {
                "success": False,
                "artifact_type": mock["artifact_type"],
                "content": {"error": f"Agent {agent_type} failed on task"},
                "latency_sec": round(self._rng.uniform(0.1, 0.5), 3),
            }

        # Simulate output with optional quality variation
        content = dict(mock["template"])
        if agent_type == "critic":
            base_score = 0.85 + quality_boost
            noisy_score = base_score + self._rng.uniform(-0.1, 0.1)
            noisy_score = max(0.0, min(1.0, noisy_score))
            content["score"] = round(noisy_score, 3)
            content["pass"] = noisy_score >= 0.6

        latency = round(self._rng.uniform(0.05, 0.3), 3)

        return {
            "success": True,
            "artifact_type": mock["artifact_type"],
            "content": content,
            "latency_sec": latency,
        }
