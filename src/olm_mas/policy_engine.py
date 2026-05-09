"""Policy engine for access control and constraint enforcement.

Evaluates PolicyRules to determine what an agent is allowed to do.
Hard constraints are never overridable by the orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .schemas import PolicyRule


# Default policy rules applied to every workflow
DEFAULT_POLICIES: list[dict] = [
    {
        "rule_id": "deny-external-send",
        "subject_scope": "*",
        "object_scope": "external_send",
        "action": "deny",
        "priority": 100,
        "is_hard_constraint": True,
    },
    {
        "rule_id": "deny-destructive-action",
        "subject_scope": "*",
        "object_scope": "destructive_action",
        "action": "deny",
        "priority": 100,
        "is_hard_constraint": True,
    },
    {
        "rule_id": "allow-read-blackboard",
        "subject_scope": "*",
        "object_scope": "read_blackboard",
        "action": "allow",
        "priority": 0,
        "is_hard_constraint": False,
    },
]


class PolicyEngine:
    """Evaluates policy rules to produce allow/deny decisions."""

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        if rules is None:
            rules = [PolicyRule(**d) for d in DEFAULT_POLICIES]
        self._rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    @property
    def rules(self) -> list[PolicyRule]:
        return list(self._rules)

    def add_rule(self, rule: PolicyRule) -> bool:
        """Add a policy rule.

        Returns:
            True if added, False if rejected because it conflicts with
            an existing hard deny constraint.
        """
        if rule.action == "allow":
            for existing in self._rules:
                if existing.action != "deny" or not existing.is_hard_constraint:
                    continue
                if self._is_expired(existing):
                    continue
                if not self._scopes_overlap(existing.subject_scope, rule.subject_scope):
                    continue
                if not self._scopes_overlap(existing.object_scope, rule.object_scope):
                    continue
                return False
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        return True

    def check(
        self,
        agent_type: str,
        resource: str,
        action: str = "use",
    ) -> tuple[bool, str, list[str]]:
        """Check whether *agent_type* may perform *action* on *resource*.

        Returns (allowed, reason, matching_rule_ids).
        """
        # Hard denies always win, independent of priority ordering.
        for rule in self._rules:
            if rule.action != "deny" or not rule.is_hard_constraint:
                continue
            if self._is_expired(rule):
                continue
            if not self._scope_matches(rule.subject_scope, agent_type):
                continue
            if not self._scope_matches(rule.object_scope, resource):
                continue
            return False, f"Denied by hard rule {rule.rule_id}", [rule.rule_id]

        matched_ids: list[str] = []
        for rule in self._rules:
            if rule.action == "deny" and rule.is_hard_constraint:
                continue
            if not self._scope_matches(rule.subject_scope, agent_type):
                continue
            if not self._scope_matches(rule.object_scope, resource):
                continue
            if self._is_expired(rule):
                continue
            matched_ids.append(rule.rule_id)
            if rule.action == "deny":
                label = "hard" if rule.is_hard_constraint else "soft"
                return False, f"Denied by {label} rule {rule.rule_id}", matched_ids
            if rule.action == "allow":
                return True, f"Allowed by rule {rule.rule_id}", matched_ids

        # Default allow if no matching rule
        return True, "No matching rule — default allow", matched_ids

    def filter_tools(
        self,
        agent_type: str,
        requested_tools: list[str],
    ) -> list[str]:
        """Return the subset of *requested_tools* the agent is allowed to use."""
        return [
            tool for tool in requested_tools
            if self.check(agent_type, tool)[0]
        ]

    # ------------------------------------------------------------------

    @staticmethod
    def _scope_matches(scope: str, value: str) -> bool:
        if scope == "*":
            return True
        return scope == value

    @staticmethod
    def _scopes_overlap(scope_a: str, scope_b: str) -> bool:
        if scope_a == "*" or scope_b == "*":
            return True
        return scope_a == scope_b

    @staticmethod
    def _is_expired(rule: PolicyRule) -> bool:
        return bool(rule.expiry and rule.expiry < datetime.now(timezone.utc))
