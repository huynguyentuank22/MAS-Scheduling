"""Agent runtime with schema-validated outputs.

Mock runtime behavior is preserved while all outputs pass through
LLMOutputParser and AgentOutput validation.
"""

from __future__ import annotations

import random
from typing import Any

from .llm_output_parser import LLMOutputParser
from .schemas import AgentOutput, AgentOutputStatus, AgentProfile


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
    "tool_executor": {
        "artifact_type": "tool_result",
        "template": {
            "tool_calls": ["search"],
            "result": "Tool execution completed",
        },
    },
    "calculator": {
        "artifact_type": "calculation",
        "template": {
            "expression": "2+2",
            "result": 4,
        },
    },
    "file_reader": {
        "artifact_type": "file_notes",
        "template": {
            "filename": "sample.txt",
            "summary": "Read and summarized file contents.",
        },
    },
    "writer": {
        "artifact_type": "draft",
        "template": {
            "draft_text": "Draft output based on evidence and task context.",
            "word_count": 150,
        },
    },
    "verifier": {
        "artifact_type": "verification",
        "template": {
            "checks": ["consistency", "constraints"],
            "pass": True,
            "score": 0.85,
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
    """Simulates agent execution and returns schema-validated output."""

    def __init__(
        self,
        seed: int = 42,
        failure_rate: float = 0.10,
        output_parser: LLMOutputParser | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._failure_rate = failure_rate
        self._parser = output_parser or LLMOutputParser()

    def run(
        self,
        profile: AgentProfile,
        task_description: str,
        context: dict[str, Any] | None = None,
        quality_boost: float = 0.0,
    ) -> dict[str, Any]:
        """Run an agent and return validated output with runtime metadata."""
        del context  # reserved for future real runtime wiring.

        raw_output, fallback_artifact_type, latency = self._generate_raw_output(
            profile=profile,
            task_description=task_description,
            quality_boost=quality_boost,
        )
        parsed = self._parser.parse(raw_output, default_artifact_type=fallback_artifact_type)
        parse_meta = self._parser.last_metrics

        success = bool(
            parsed.schema_valid
            and parsed.status in {AgentOutputStatus.SUCCESS, AgentOutputStatus.PARTIAL_SUCCESS}
        )

        return {
            "success": success,
            "artifact_type": parsed.artifact_type,
            "content": parsed.artifact_payload,
            "latency_sec": latency,
            "agent_output": parsed,
            "parse_meta": parse_meta,
        }

    def _generate_raw_output(
        self,
        profile: AgentProfile,
        task_description: str,
        quality_boost: float,
    ) -> tuple[Any, str, float]:
        agent_type = profile.agent_type
        mock = _MOCK_OUTPUTS.get(
            agent_type,
            {
                "artifact_type": "generic",
                "template": {"output": "generic output"},
            },
        )
        latency = round(self._rng.uniform(0.05, 0.3), 3)

        if self._rng.random() < self._failure_rate:
            return (
                {
                    "status": "failed",
                    "summary": f"Agent {agent_type} failed on task",
                    "artifact_type": mock["artifact_type"],
                    "artifact_payload": {"error": f"Agent {agent_type} failed on task"},
                    "confidence": 0.0,
                    "uncertainties": ["execution_failure"],
                },
                mock["artifact_type"],
                latency,
            )

        content = dict(mock["template"])
        confidence = 0.75
        uncertainties: list[str] = []

        if agent_type == "critic":
            base_score = 0.85 + quality_boost
            noisy_score = base_score + self._rng.uniform(-0.1, 0.1)
            noisy_score = max(0.0, min(1.0, noisy_score))
            content["score"] = round(noisy_score, 3)
            content["pass"] = noisy_score >= 0.6
            confidence = max(0.0, min(1.0, noisy_score))

        summary = f"{agent_type} completed task: {task_description[:80]}"

        return (
            {
                "status": "success",
                "summary": summary,
                "artifact_type": mock["artifact_type"],
                "artifact_payload": content,
                "confidence": round(confidence, 3),
                "uncertainties": uncertainties,
            },
            mock["artifact_type"],
            latency,
        )


class NoisyLLMRuntime(AgentRuntime):
    """Runtime that emits noisy LLM-like outputs for parser/curation robustness tests."""

    def __init__(
        self,
        seed: int = 42,
        failure_rate: float = 0.0,
        output_parser: LLMOutputParser | None = None,
        noise_mode: str = "malformed_json",
    ) -> None:
        super().__init__(seed=seed, failure_rate=failure_rate, output_parser=output_parser)
        self._noise_mode = noise_mode

    def _generate_raw_output(
        self,
        profile: AgentProfile,
        task_description: str,
        quality_boost: float,
    ) -> tuple[Any, str, float]:
        base_output, fallback_artifact_type, latency = super()._generate_raw_output(
            profile=profile,
            task_description=task_description,
            quality_boost=quality_boost,
        )

        if self._noise_mode == "malformed_json":
            malformed = (
                '{"status":"success","summary":"Recovered JSON","artifact_type":"'
                + fallback_artifact_type
                + '","artifact_payload":{"text":"ok",},"confidence":0.6,"uncertainties":[]}'
            )
            return malformed, fallback_artifact_type, latency

        if self._noise_mode == "missing_fields":
            missing = {
                "status": "success",
                "artifact_type": fallback_artifact_type,
                "confidence": 0.7,
            }
            return missing, fallback_artifact_type, latency

        if self._noise_mode == "hallucinated_artifact_ref":
            hallucinated = {
                "status": "success",
                "summary": "Looks valid but injects runtime field",
                "artifact_type": fallback_artifact_type,
                "artifact_payload": {"text": "danger"},
                "confidence": 0.7,
                "uncertainties": [],
                "artifact_id": "llm-fake-artifact-id",
            }
            return hallucinated, fallback_artifact_type, latency

        if self._noise_mode == "overgeneralized_lesson":
            lesson_payload = {
                "status": "success",
                "summary": "Always call critic first for every task",
                "artifact_type": "lesson",
                "artifact_payload": {
                    "lesson": "always call critic",
                    "rule": "always call critic",
                    "scope": "all tasks",
                },
                "confidence": 0.95,
                "uncertainties": [],
            }
            return lesson_payload, "lesson", latency

        return base_output, fallback_artifact_type, latency
