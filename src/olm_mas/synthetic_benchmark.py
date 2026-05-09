"""Synthetic benchmark family specs and seeded procedural memories."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SYNTHETIC_TASK_FAMILIES: dict[str, dict[str, Any]] = {
    "research_report": {
        "objective": "Produce a research report on a given topic",
        "tasks": [
            "Plan the research structure",
            "Research and gather evidence",
            "Write the initial draft",
            "Verify and critique the draft",
        ],
        "difficulty": 0.3,
    },
    "data_analysis": {
        "objective": "Analyse a dataset and produce findings",
        "tasks": [
            "Plan the analysis approach",
            "Gather and inspect data",
            "Execute analysis and write results",
            "Review and verify findings",
        ],
        "difficulty": 0.4,
    },
    "code_review": {
        "objective": "Review code changes and produce a report",
        "tasks": [
            "Plan review criteria",
            "Browse and gather code context",
            "Draft review comments",
            "Verify review completeness",
        ],
        "difficulty": 0.35,
    },
    "troubleshooting": {
        "objective": "Diagnose and fix a reported issue",
        "tasks": [
            "Plan diagnostic approach",
            "Gather evidence and logs",
            "Execute fix attempt",
            "Verify fix and write summary",
        ],
        "difficulty": 0.5,
    },
    "content_creation": {
        "objective": "Create structured content from requirements",
        "tasks": [
            "Plan content structure",
            "Research supporting material",
            "Draft the content",
            "Review and polish",
        ],
        "difficulty": 0.25,
    },
    # Hard families with orchestration traps.
    "evidence_based_writing": {
        "objective": "Produce evidence-backed content under ambiguous instructions",
        "tasks": [
            "Draft a compelling answer quickly using available clues",
            "Inspect source snippets and collect evidence",
            "Write the final evidence-backed response",
            "Verify claims against gathered evidence",
        ],
        "difficulty": 0.65,
        "constraints": {
            "required_order": [["researcher", "writer"]],
            "required_agents": ["researcher", "writer", "critic"],
            "avoid_patterns": ["writer_before_evidence_complete"],
            "penalties": {
                "writer_before_researcher": 0.25,
                "missing_required_agent": 0.15,
                "unnecessary_repeated_call": 0.05,
            },
        },
    },
    "multi_source_conflict": {
        "objective": "Resolve conflicting sources and produce a validated conclusion",
        "tasks": [
            "Draft a merged conclusion from conflicting notes",
            "Gather source evidence and contradictions",
            "Verify consistency and resolve conflicts",
            "Write the reconciled final answer",
        ],
        "difficulty": 0.7,
        "constraints": {
            "required_order": [["researcher", "critic"], ["critic", "writer"]],
            "required_agents": ["researcher", "critic", "writer"],
            "avoid_patterns": ["writer_before_critic", "writer_before_evidence_complete"],
            "penalties": {
                "writer_before_critic": 0.3,
                "writer_before_researcher": 0.2,
                "missing_required_agent": 0.15,
                "unnecessary_repeated_call": 0.05,
            },
        },
    },
    "form_submission": {
        "objective": "Complete and submit a structured form without compliance errors",
        "tasks": [
            "Submit the form response quickly",
            "Gather required fields and supporting details",
            "Check required fields and policy constraints",
            "Finalize submission confirmation",
        ],
        "difficulty": 0.6,
        "constraints": {
            "required_order": [["researcher", "critic"], ["critic", "writer"]],
            "required_agents": ["researcher", "critic", "writer"],
            "avoid_patterns": ["submit_before_required_field_check", "finalize_without_verifier"],
            "penalties": {
                "submit_before_checker": 0.3,
                "finalize_without_verifier": 0.2,
                "missing_required_agent": 0.15,
                "unnecessary_repeated_call": 0.05,
            },
        },
    },
    "debugging": {
        "objective": "Diagnose issue and patch only after reproducing and inspecting evidence",
        "tasks": [
            "Patch the issue quickly based on symptoms",
            "Reproduce the bug and inspect logs",
            "Verify patch impact and regressions",
            "Write final fix summary",
        ],
        "difficulty": 0.75,
        "constraints": {
            "required_order": [["researcher", "writer"], ["critic", "writer"]],
            "required_agents": ["researcher", "critic", "writer"],
            "avoid_patterns": ["patch_before_reproduce"],
            "penalties": {
                "patch_before_reproduce": 0.3,
                "missing_required_agent": 0.15,
                "unnecessary_repeated_call": 0.05,
            },
        },
    },
    "dynamic_recovery": {
        "objective": "Handle failing strategy with adaptive recovery rather than repeated retries",
        "tasks": [
            "Execute the current approach despite instability",
            "Inspect failure signals and root causes",
            "Retry the same strategy until it works",
            "Summarize recovery and final outcome",
        ],
        "difficulty": 0.8,
        "constraints": {
            "required_agents": ["researcher", "recovery", "writer"],
            "avoid_patterns": ["retry_same_failed_strategy"],
            "recovery_rules": [
                {
                    "when_action": "retry",
                    "min_retry_count": 1,
                    "action": "recovery_agent",
                    "reason": "Escalate to recovery after failed retry",
                }
            ],
            "penalties": {
                "retry_same_failed_strategy": 0.35,
                "missing_recovery_agent": 0.2,
                "missing_required_agent": 0.1,
                "unnecessary_repeated_call": 0.05,
            },
        },
    },
}


def get_family_spec(task_family: str | None) -> dict[str, Any]:
    if not task_family:
        return {}
    return deepcopy(SYNTHETIC_TASK_FAMILIES.get(task_family, {}))


def get_seed_memories() -> dict[str, dict[str, Any]]:
    """Seed memories keyed by family for the hard benchmark families."""
    return {
        "evidence_based_writing": {
            "trigger": {"task_family": "evidence_based_writing", "benchmark": "synthetic"},
            "recommended_schedule": ["researcher", "writer", "critic"],
            "avoid": [{"action": "writer_before_evidence_complete"}],
            "recommended_recovery": [],
            "confidence": 0.8,
        },
        "multi_source_conflict": {
            "trigger": {"task_family": "multi_source_conflict", "benchmark": "synthetic"},
            "recommended_schedule": ["researcher", "critic", "writer"],
            "avoid": [
                {"action": "writer_before_critic"},
                {"action": "writer_before_evidence_complete"},
            ],
            "recommended_recovery": [],
            "confidence": 0.85,
        },
        "form_submission": {
            "trigger": {"task_family": "form_submission", "benchmark": "synthetic"},
            "recommended_schedule": ["researcher", "critic", "writer"],
            "avoid": [
                {"action": "submit_before_required_field_check"},
                {"action": "finalize_without_verifier"},
            ],
            "recommended_recovery": [],
            "confidence": 0.82,
        },
        "debugging": {
            "trigger": {"task_family": "debugging", "benchmark": "synthetic"},
            "recommended_schedule": ["researcher", "critic", "writer"],
            "avoid": [{"action": "patch_before_reproduce"}],
            "recommended_recovery": [],
            "confidence": 0.83,
        },
        "dynamic_recovery": {
            "trigger": {"task_family": "dynamic_recovery", "benchmark": "synthetic"},
            "recommended_schedule": ["researcher", "recovery", "writer"],
            "avoid": [{"action": "retry_same_failed_strategy"}],
            "recommended_recovery": [
                {
                    "when_action": "retry",
                    "min_retry_count": 1,
                    "action": "recovery_agent",
                    "reason": "Escalate after repeated retry",
                }
            ],
            "confidence": 0.88,
        },
    }
