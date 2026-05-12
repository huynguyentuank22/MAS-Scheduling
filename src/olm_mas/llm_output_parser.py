"""LLM output parsing, repair, and schema validation."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .schemas import AgentOutput, AgentOutputStatus, _uuid


_REQUIRED_LLM_FIELDS = {
    "status",
    "summary",
    "artifact_type",
    "artifact_payload",
    "confidence",
}

_RUNTIME_OWNED_FIELDS = {
    "workflow_id",
    "task_id",
    "agent_id",
    "decision_id",
    "action_type",
    "artifact_id",
    "input_refs",
    "output_refs",
    "timestamp",
    "latency_sec",
    "cost",
    "policy_refs",
    "memory_refs",
}

_PARSER_OWNED_FIELDS = {
    "raw_output_ref",
    "schema_valid",
    "validation_errors",
    "repair_attempt_count",
}


class LLMOutputParser:
    """Parses raw LLM output, attempts one repair, and validates AgentOutput."""

    def __init__(self) -> None:
        self._raw_outputs: dict[str, str] = {}
        self._last_metrics: dict[str, Any] = {
            "parse_failed": False,
            "repair_attempted": False,
            "repair_succeeded": False,
            "invalid_runtime_fields": [],
        }

    @property
    def last_metrics(self) -> dict[str, Any]:
        return dict(self._last_metrics)

    def get_raw_output(self, raw_output_ref: str) -> str | None:
        return self._raw_outputs.get(raw_output_ref)

    def parse(
        self,
        raw_output: Any,
        default_artifact_type: str = "generic",
    ) -> AgentOutput:
        raw_ref = _uuid()
        raw_text = self._to_text(raw_output)
        self._raw_outputs[raw_ref] = raw_text
        self._last_metrics = {
            "parse_failed": False,
            "repair_attempted": False,
            "repair_succeeded": False,
            "invalid_runtime_fields": [],
        }

        payload: dict[str, Any] | None = None
        repair_attempt_count = 0
        errors: list[str] = []

        if isinstance(raw_output, AgentOutput):
            payload = raw_output.model_dump()
        elif isinstance(raw_output, dict):
            payload = dict(raw_output)
        elif isinstance(raw_output, str):
            payload = self._parse_json_object(raw_output)
            if payload is None:
                self._last_metrics["parse_failed"] = True
                self._last_metrics["repair_attempted"] = True
                repair_attempt_count = 1
                repaired = self._repair_once(raw_output)
                payload = self._parse_json_object(repaired)
                if payload is not None:
                    self._last_metrics["repair_succeeded"] = True
                else:
                    errors.append("malformed_json_after_repair")
        else:
            errors.append("unsupported_raw_output_type")

        if payload is None:
            return self._invalid_output(
                raw_output_ref=raw_ref,
                validation_errors=errors or ["unable_to_parse_output"],
                repair_attempt_count=repair_attempt_count,
            )

        # Runtime-owned fields from model output are rejected.
        disallowed_fields = sorted(
            set(payload.keys()).intersection(_RUNTIME_OWNED_FIELDS | _PARSER_OWNED_FIELDS)
        )
        if disallowed_fields:
            self._last_metrics["invalid_runtime_fields"] = disallowed_fields
            errors.extend([f"runtime_field_not_allowed:{field}" for field in disallowed_fields])
            for field in disallowed_fields:
                payload.pop(field, None)

        missing_required = sorted(_REQUIRED_LLM_FIELDS - set(payload.keys()))
        if missing_required:
            errors.extend([f"missing_field:{field}" for field in missing_required])

        # Build candidate with strict status parsing but resilient defaults.
        candidate = {
            "status": payload.get("status", AgentOutputStatus.INVALID.value),
            "summary": payload.get("summary", ""),
            "artifact_type": payload.get("artifact_type", default_artifact_type),
            "artifact_payload": payload.get("artifact_payload", {}),
            "confidence": payload.get("confidence", 0.0),
            "uncertainties": payload.get("uncertainties", []),
            "requested_next_action": payload.get("requested_next_action"),
            "raw_output_ref": raw_ref,
            "schema_valid": False,
            "validation_errors": [],
            "repair_attempt_count": repair_attempt_count,
        }

        try:
            parsed = AgentOutput.model_validate(candidate)
        except ValidationError as exc:
            errors.append(f"schema_validation_error:{exc.errors()}")
            return self._invalid_output(
                raw_output_ref=raw_ref,
                validation_errors=errors,
                repair_attempt_count=repair_attempt_count,
            )

        if errors:
            parsed.status = AgentOutputStatus.INVALID
            parsed.schema_valid = False
            parsed.validation_errors = errors
            return parsed

        parsed.schema_valid = True
        parsed.validation_errors = []
        return parsed

    def _invalid_output(
        self,
        raw_output_ref: str,
        validation_errors: list[str],
        repair_attempt_count: int,
    ) -> AgentOutput:
        return AgentOutput(
            status=AgentOutputStatus.INVALID,
            summary="Invalid or malformed agent output",
            artifact_type="invalid_output",
            artifact_payload={},
            confidence=0.0,
            uncertainties=[],
            raw_output_ref=raw_output_ref,
            schema_valid=False,
            validation_errors=validation_errors,
            repair_attempt_count=repair_attempt_count,
        )

    @staticmethod
    def _to_text(raw_output: Any) -> str:
        if isinstance(raw_output, str):
            return raw_output
        try:
            return json.dumps(raw_output, default=str)
        except Exception:
            return str(raw_output)

    @staticmethod
    def _parse_json_object(value: str) -> dict[str, Any] | None:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(decoded, dict):
            return decoded
        return None

    @staticmethod
    def _repair_once(value: str) -> str:
        repaired = value.strip()

        # Remove markdown code fences.
        repaired = re.sub(r"^```(?:json)?\s*", "", repaired, flags=re.IGNORECASE)
        repaired = re.sub(r"\s*```$", "", repaired)

        # Keep object span if extra chatter exists.
        start = repaired.find("{")
        end = repaired.rfind("}")
        if start != -1 and end != -1 and end > start:
            repaired = repaired[start : end + 1]

        # Remove trailing commas before object/array terminators.
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        return repaired
