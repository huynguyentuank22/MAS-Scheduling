"""Tests for policy engine behavior and hard-constraint protection."""

from datetime import datetime, timedelta, timezone

from olm_mas.policy_engine import PolicyEngine
from olm_mas.schemas import PolicyRule


def test_policy_hard_constraint_protection():
    engine = PolicyEngine()

    # add_rule should reject conflicting allow over hard deny
    added = engine.add_rule(
        PolicyRule(
            subject_scope="*",
            object_scope="external_send",
            action="allow",
            priority=999,
        )
    )
    assert added is False

    allowed, reason, _ = engine.check("writer", "external_send")
    assert allowed is False
    assert "hard rule" in reason

    # Hard deny must win regardless of priority ordering
    engine2 = PolicyEngine(
        rules=[
            PolicyRule(
                rule_id="allow-high",
                subject_scope="*",
                object_scope="execute_task",
                action="allow",
                priority=500,
            ),
            PolicyRule(
                rule_id="deny-hard-low",
                subject_scope="*",
                object_scope="execute_task",
                action="deny",
                priority=1,
                is_hard_constraint=True,
            ),
        ]
    )
    allowed2, reason2, matched2 = engine2.check("writer", "execute_task")
    assert allowed2 is False
    assert matched2 == ["deny-hard-low"]
    assert "hard rule" in reason2


def test_policy_tool_filtering():
    engine = PolicyEngine()
    added = engine.add_rule(
        PolicyRule(
            rule_id="deny-run-checks",
            subject_scope="writer",
            object_scope="run_checks",
            action="deny",
            priority=100,
        )
    )
    assert added is True

    tools = ["read_blackboard", "run_checks", "write_artifact"]
    filtered = engine.filter_tools("writer", tools)

    assert "run_checks" not in filtered
    assert "read_blackboard" in filtered
    assert "write_artifact" in filtered


def test_policy_expiry():
    engine = PolicyEngine(
        rules=[
            PolicyRule(
                rule_id="expired-deny",
                subject_scope="*",
                object_scope="temporary_tool",
                action="deny",
                priority=100,
                expiry=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        ]
    )

    allowed, reason, matched = engine.check("writer", "temporary_tool")
    assert allowed is True
    assert matched == []
    assert "default allow" in reason
