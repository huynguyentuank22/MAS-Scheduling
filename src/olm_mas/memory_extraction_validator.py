"""Validation guardrails for procedural memory extraction/update."""

from __future__ import annotations

from typing import Any

from .agent_registry import AgentRegistry
from .schemas import DecisionEvent, ProceduralControlMemory, SchedulingEvaluation, WorkflowSession


class MemoryExtractionValidator:
    """Validates whether a procedural memory is supported by episode evidence."""

    def validate(
        self,
        memory: ProceduralControlMemory,
        workflow: WorkflowSession,
        evaluation: SchedulingEvaluation,
        decisions: list[DecisionEvent],
        registry: AgentRegistry,
        prior_confidence: float | None = None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        categories: set[str] = set()

        task_family = str(memory.trigger.get("task_family") or "").strip()
        if not task_family:
            reasons.append("trigger.task_family_missing")
            categories.add("unsupported")

        valid_agents = {p.agent_type for p in registry.list_agents()}
        invalid_agents = [a for a in memory.recommended_schedule if a not in valid_agents]
        if invalid_agents:
            reasons.append(f"recommended_schedule_unknown_agents:{','.join(invalid_agents)}")
            categories.add("unsupported")

        if not memory.supporting_episodes:
            reasons.append("supporting_episodes_empty")
            categories.add("unsupported")

        failure_signals = {str(f) for f in evaluation.failure_factors}
        trace_signals = self._trace_signals(decisions)

        avoid_patterns = self._extract_patterns(memory.avoid)
        if avoid_patterns:
            supported_avoid = any(self._pattern_supported(p, failure_signals, trace_signals) for p in avoid_patterns)
            if not supported_avoid:
                reasons.append("unsupported_avoid_pattern")
                categories.add("unsupported")

        if memory.recommended_recovery and not self._recovery_supported(decisions):
            reasons.append("unsupported_recovery_rule")
            categories.add("unsupported")

        if self._is_overgeneralized(memory):
            reasons.append("overgeneralized_memory_rule")
            categories.add("overgeneralized")

        schema_valid_rate = float(evaluation.scheduling_scores.get("agent_output_schema_valid_rate", 1.0))
        parse_failure_rate = float(evaluation.scheduling_scores.get("parse_failure_rate", 0.0))

        if prior_confidence is not None and memory.confidence > prior_confidence:
            if schema_valid_rate < 1.0 or parse_failure_rate > 0.0:
                reasons.append("confidence_increase_blocked_due_to_invalid_output_evidence")
                categories.add("unsupported")
            if categories:
                reasons.append("confidence_increase_not_supported_by_valid_episode_evidence")
                categories.add("unsupported")

        accepted = len(reasons) == 0
        return {
            "accepted": accepted,
            "reason": "ok" if accepted else ";".join(reasons),
            "categories": sorted(categories),
            "overgeneralized": "overgeneralized" in categories,
            "unsupported": "unsupported" in categories,
        }

    @staticmethod
    def _extract_patterns(avoid: list[dict[str, Any]] | list[Any]) -> set[str]:
        patterns: set[str] = set()
        for item in avoid:
            if isinstance(item, str):
                patterns.add(item)
                continue
            if isinstance(item, dict):
                action = item.get("action")
                if isinstance(action, str):
                    patterns.add(action)
                pattern = item.get("pattern")
                if isinstance(pattern, str):
                    patterns.add(pattern)
        return patterns

    @staticmethod
    def _trace_signals(decisions: list[DecisionEvent]) -> set[str]:
        signals: set[str] = set()
        for d in decisions:
            action = str(d.chosen_action or "")
            if action:
                signals.add(action)
            rationale = str(d.rationale_summary or "").lower()
            if "retry" in rationale:
                signals.add("retry")
            if "recovery" in rationale:
                signals.add("recovery")
            if "verify" in rationale or "critic" in rationale:
                signals.add("verify")
        return signals

    @staticmethod
    def _pattern_supported(pattern: str, failure_signals: set[str], trace_signals: set[str]) -> bool:
        normalized = pattern.strip().lower()
        if normalized in failure_signals or normalized in trace_signals:
            return True
        # Map high-level lesson names to known episode signals.
        if normalized in {"writer_before_critic", "writer_before_evidence_complete"}:
            return "order_violations" in failure_signals or "verify" in trace_signals
        if normalized in {"finalize_without_verifier", "submit_before_required_field_check"}:
            return "order_violations" in failure_signals or "finalize" in trace_signals
        if normalized == "retry_same_failed_strategy":
            return "excessive_retries" in failure_signals or "retry" in trace_signals
        return False

    @staticmethod
    def _recovery_supported(decisions: list[DecisionEvent]) -> bool:
        actions = [str(d.chosen_action or "") for d in decisions]
        return "retry" in actions or "call_recovery_agent" in actions

    @staticmethod
    def _is_overgeneralized(memory: ProceduralControlMemory) -> bool:
        trigger = memory.trigger or {}
        has_specificity = bool(
            trigger.get("task_pattern")
            or trigger.get("constraints")
            or trigger.get("tags")
        )
        first_agent = memory.recommended_schedule[0] if memory.recommended_schedule else ""
        if first_agent == "critic" and not has_specificity:
            return True

        for item in memory.avoid:
            if isinstance(item, str) and item.strip().lower().startswith("always "):
                return True
            if isinstance(item, dict):
                reason = str(item.get("reason") or "").strip().lower()
                if reason.startswith("always "):
                    return True
        return False
