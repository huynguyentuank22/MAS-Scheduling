"""Agent runtime with schema-validated outputs.

Mock runtime behavior is preserved while all outputs pass through
LLMOutputParser and AgentOutput validation.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any

import requests

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

_ORACLE_ANSWER_PATTERN = re.compile(r"\[ORACLE_EXPECTED_ANSWER=(.*?)\]", re.IGNORECASE)
_ORACLE_TASK_ID_PATTERN = re.compile(r"\[ORACLE_TASK_ID=(.*?)\]", re.IGNORECASE)
_ORACLE_FAMILY_PATTERN = re.compile(r"\[ORACLE_TASK_FAMILY=(.*?)\]", re.IGNORECASE)


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


class LLMAgentRuntime(AgentRuntime):
    """LLM-backed runtime with strict JSON output and schema validation."""

    _ROLE_PROMPTS: dict[str, str] = {
        "planner": (
            "You are a planning agent for GAIA-lite tasks.\n"
            "Return ONLY JSON matching this schema:\n"
            "{"
            "\"status\":\"success|partial_success|failed\","
            "\"summary\":\"short text\","
            "\"artifact_type\":\"plan\","
            "\"artifact_payload\":{...},"
            "\"confidence\":0.0_to_1.0,"
            "\"uncertainties\":[\"...\"]"
            "}\n"
            "Do not include any runtime-owned fields."
        ),
        "researcher": (
            "You are a research agent. Gather evidence and findings.\n"
            "Return ONLY JSON with artifact_type as evidence/tool_result/file_notes as appropriate.\n"
            "Do not include any runtime-owned fields."
        ),
        "writer": (
            "You are a writer agent.\n"
            "If this step asks for final answer or return-only answer, use artifact_type='final_answer' "
            "and artifact_payload must include {\"answer\": \"...\"}.\n"
            "Otherwise use artifact_type='draft'.\n"
            "Return ONLY valid JSON matching AgentOutput fields."
        ),
        "critic": (
            "You are a verifier/critic agent.\n"
            "Check consistency and constraints.\n"
            "If this step is final verification, you may emit artifact_type='final_answer' with "
            "artifact_payload.answer.\n"
            "Return ONLY valid JSON matching AgentOutput fields."
        ),
        "verifier": (
            "You are a verifier agent.\n"
            "Check consistency and constraints.\n"
            "If this step is final verification, you may emit artifact_type='final_answer' with "
            "artifact_payload.answer.\n"
            "Return ONLY valid JSON matching AgentOutput fields."
        ),
    }

    _RUNTIME_OWNED_FIELDS = (
        "workflow_id, task_id, agent_id, decision_id, action_type, artifact_id, input_refs, output_refs, "
        "timestamp, latency_sec, cost, policy_refs, memory_refs"
    )

    def __init__(
        self,
        seed: int = 42,
        failure_rate: float = 0.0,
        output_parser: LLMOutputParser | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 400,
        require_json_output: bool = True,
        api_key: str | None = None,
        api_base_url: str | None = None,
        timeout_sec: float = 45.0,
        request_func: Any | None = None,
    ) -> None:
        super().__init__(seed=seed, failure_rate=failure_rate, output_parser=output_parser)
        provider = (llm_provider or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
        model = (llm_model or os.getenv("LLM_MODEL") or "gpt-4.1-mini").strip()

        self._llm_provider = provider
        self._llm_model = model
        self._temperature = float(temperature)
        self._max_tokens = int(max_tokens)
        self._require_json_output = bool(require_json_output)
        self._timeout_sec = float(timeout_sec)
        self._request_func = request_func or requests.post

        default_base = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self._api_base_url = (api_base_url or default_base).rstrip("/")
        self._api_key = (
            api_key
            or os.getenv("LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        self._setup_error = self._validate_setup()

    def _generate_raw_output(
        self,
        profile: AgentProfile,
        task_description: str,
        quality_boost: float,
    ) -> tuple[Any, str, float]:
        del quality_boost
        fallback = _MOCK_OUTPUTS.get(profile.agent_type, {}).get("artifact_type", "generic")

        if self._setup_error:
            return (
                {
                    "status": "failed",
                    "summary": self._setup_error,
                    "artifact_type": fallback,
                    "artifact_payload": {"error": self._setup_error},
                    "confidence": 0.0,
                    "uncertainties": ["llm_setup_error"],
                },
                fallback,
                0.0,
            )

        started = time.perf_counter()
        try:
            raw_content = self._call_provider(profile=profile, task_description=task_description)
            latency = round(time.perf_counter() - started, 3)
            return raw_content, fallback, latency
        except Exception as exc:
            message = f"llm_provider_call_failed: {exc}"
            latency = round(time.perf_counter() - started, 3)
            return (
                {
                    "status": "failed",
                    "summary": message,
                    "artifact_type": fallback,
                    "artifact_payload": {"error": message},
                    "confidence": 0.0,
                    "uncertainties": ["llm_provider_error"],
                },
                fallback,
                latency,
            )

    def _validate_setup(self) -> str | None:
        if self._llm_provider not in {"openai", "openai_compatible"}:
            return (
                f"Unsupported llm_provider='{self._llm_provider}'. "
                "Supported: openai, openai_compatible."
            )
        if not self._api_key:
            return (
                "LLM API key missing: set OPENAI_API_KEY or LLM_API_KEY "
                "for runtime_mode=llm."
            )
        if not self._llm_model:
            return "LLM model missing: set --llm-model or LLM_MODEL."
        return None

    @property
    def setup_error(self) -> str | None:
        return self._setup_error

    @property
    def llm_provider(self) -> str:
        return self._llm_provider

    @property
    def llm_model(self) -> str:
        return self._llm_model

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def require_json_output(self) -> bool:
        return self._require_json_output

    def _call_provider(self, profile: AgentProfile, task_description: str) -> str:
        if self._llm_provider in {"openai", "openai_compatible"}:
            return self._call_openai_compatible(profile=profile, task_description=task_description)
        raise RuntimeError(f"unsupported_provider:{self._llm_provider}")

    def _call_openai_compatible(self, profile: AgentProfile, task_description: str) -> str:
        system_prompt = self._build_system_prompt(profile.agent_type)
        user_prompt = self._build_user_prompt(task_description)
        url = f"{self._api_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if self._require_json_output:
            payload["response_format"] = {"type": "json_object"}

        response = self._request_func(
            url,
            headers=headers,
            json=payload,
            timeout=self._timeout_sec,
        )

        if int(getattr(response, "status_code", 500)) >= 400 and self._require_json_output:
            retry_payload = dict(payload)
            retry_payload.pop("response_format", None)
            response = self._request_func(
                url,
                headers=headers,
                json=retry_payload,
                timeout=self._timeout_sec,
            )

        status_code = int(getattr(response, "status_code", 500))
        if status_code >= 400:
            body = getattr(response, "text", "")
            raise RuntimeError(f"http_{status_code}:{body[:300]}")

        try:
            data = response.json()
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"invalid_json_response:{exc}") from exc

        # OpenAI Chat Completions shape
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content

        # OpenAI Responses API-like shape fallback
        output = data.get("output")
        if isinstance(output, list) and output:
            for item in output:
                contents = item.get("content") if isinstance(item, dict) else None
                if not isinstance(contents, list):
                    continue
                for chunk in contents:
                    text = (chunk or {}).get("text") if isinstance(chunk, dict) else None
                    if isinstance(text, str) and text.strip():
                        return text

        raise RuntimeError("empty_llm_content")

    def _build_system_prompt(self, agent_type: str) -> str:
        role = self._ROLE_PROMPTS.get(agent_type, self._ROLE_PROMPTS.get("writer", ""))
        return (
            f"{role}\n"
            "Strict requirements:\n"
            "1) Return JSON only, no markdown fences, no prose.\n"
            "2) Include fields: status, summary, artifact_type, artifact_payload, confidence, uncertainties.\n"
            "3) status must be one of success|partial_success|failed.\n"
            "4) confidence must be between 0 and 1.\n"
            f"5) Never include runtime-owned fields: {self._RUNTIME_OWNED_FIELDS}.\n"
        )

    @staticmethod
    def _build_user_prompt(task_description: str) -> str:
        return (
            "Task description:\n"
            f"{task_description}\n\n"
            "Produce your structured result as valid JSON only."
        )


class DeterministicGaiaLiteRuntime(AgentRuntime):
    """Oracle/smoke-only runtime for GAIA-lite sample tasks.

    This runtime is not a research result and should only be used for
    integration testing where answer-capable behavior is required.
    """

    def _generate_raw_output(
        self,
        profile: AgentProfile,
        task_description: str,
        quality_boost: float,
    ) -> tuple[Any, str, float]:
        del quality_boost
        latency = round(self._rng.uniform(0.02, 0.08), 3)
        oracle_answer = self._extract_oracle_value(_ORACLE_ANSWER_PATTERN, task_description)
        oracle_task_id = self._extract_oracle_value(_ORACLE_TASK_ID_PATTERN, task_description)
        oracle_family = self._extract_oracle_value(_ORACLE_FAMILY_PATTERN, task_description)
        task_desc_lower = (task_description or "").lower()
        agent_type = profile.agent_type

        if not oracle_answer:
            return super()._generate_raw_output(profile, task_description, 0.0)

        fallback = _MOCK_OUTPUTS.get(agent_type, {}).get("artifact_type", "generic")
        payload: dict[str, Any]
        artifact_type = fallback
        summary = f"{agent_type} completed deterministic GAIA-lite step"

        is_final_step = any(
            phrase in task_desc_lower
            for phrase in ("final answer", "write final response", "return only", "verify the final")
        )

        if agent_type in {"writer", "verifier", "critic"} or is_final_step:
            artifact_type = "final_answer"
            payload = {
                "answer": oracle_answer,
                "task_id": oracle_task_id,
                "task_family": oracle_family,
                "source": "deterministic_gaia_oracle",
            }
            summary = f"{agent_type} produced deterministic final answer"
        elif agent_type == "calculator":
            payload = {
                "computed_answer": oracle_answer,
                "task_id": oracle_task_id,
            }
        elif agent_type in {"researcher", "tool_executor", "file_reader"}:
            payload = {
                "evidence_hint": f"Prepared evidence supporting answer '{oracle_answer}'",
                "task_id": oracle_task_id,
            }
        elif agent_type == "planner":
            payload = {
                "plan": [
                    "gather_evidence",
                    "derive_answer",
                    "verify",
                    "emit_final_answer",
                ],
                "task_id": oracle_task_id,
            }
        elif agent_type == "recovery":
            payload = {
                "recommended_action": "retry",
                "retry_with_changes": ["use deterministic oracle context"],
                "task_id": oracle_task_id,
            }
        else:
            payload = {"answer": oracle_answer, "task_id": oracle_task_id}

        return (
            {
                "status": "success",
                "summary": summary,
                "artifact_type": artifact_type,
                "artifact_payload": payload,
                "confidence": 0.99,
                "uncertainties": [],
            },
            artifact_type,
            latency,
        )

    @staticmethod
    def _extract_oracle_value(pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text or "")
        if not match:
            return None
        value = match.group(1).strip()
        return value or None


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
