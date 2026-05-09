"""Scheduling evaluator - post-episode quality assessment.

Analyses decisions and task outcomes, then computes a synthetic benchmark
score with hard-family penalties to expose orchestration quality gaps.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .schemas import (
    DecisionEvent,
    SchedulingEvaluation,
    TaskNode,
    TaskState,
    WorkflowSession,
    _uuid,
)
from .synthetic_benchmark import get_family_spec


_CALL_ACTIONS = {"call_agent", "call_recovery_agent", "spawn_agent"}
_AGENT_FROM_RATIONALE = re.compile(r"(?:->|→)\s*([A-Za-z_][A-Za-z0-9_-]*)\s*$")


class SchedulingEvaluator:
    """Evaluates scheduling quality after an episode completes."""

    def evaluate(
        self,
        workflow: WorkflowSession,
        tasks: list[TaskNode],
        decisions: list[DecisionEvent],
        task_success: bool,
        benchmark_score: float = 0.0,
        memory_refs_used: list[str] | None = None,
    ) -> SchedulingEvaluation:
        """Produce a scheduling evaluation for one episode."""
        del benchmark_score  # Synthetic score is computed from observed behavior.

        done_tasks = [t for t in tasks if t.state == TaskState.DONE]
        failed_tasks = [t for t in tasks if t.state == TaskState.FAILED]
        total_tasks = len(tasks)

        retries = sum(1 for d in decisions if d.chosen_action == "retry")
        replans = sum(1 for d in decisions if d.chosen_action == "replan")
        recovery_calls = sum(1 for d in decisions if d.chosen_action == "call_recovery_agent")
        call_decisions = [d for d in decisions if d.chosen_action in _CALL_ACTIONS]
        agent_calls = len(call_decisions)

        agent_sequence = self._extract_agent_sequence(call_decisions)
        agent_first_idx = {}
        for idx, agent in enumerate(agent_sequence):
            if agent not in agent_first_idx:
                agent_first_idx[agent] = idx

        task_completion_rate = len(done_tasks) / max(total_tasks, 1)
        assignment_quality = task_completion_rate

        dep_violations = self._count_dependency_violations(tasks, decisions)
        dep_violation_rate = dep_violations / max(agent_calls, 1)

        unnecessary_no_output = sum(
            1 for d in call_decisions
            if d.chosen_action == "call_agent" and not d.output_refs
        )
        repeated_calls = sum(max(0, count - 1) for count in Counter(agent_sequence).values())
        unnecessary_calls = unnecessary_no_output + repeated_calls

        family_spec = get_family_spec(workflow.task_family)
        constraints = family_spec.get("constraints", {})
        penalties_cfg = constraints.get("penalties", {})

        order_violation_count, order_penalty = self._compute_order_penalties(
            workflow=workflow,
            decisions=decisions,
            agent_first_idx=agent_first_idx,
            constraints=constraints,
            penalties_cfg=penalties_cfg,
        )
        required_agents = list(constraints.get("required_agents", []))
        missing_required = [a for a in required_agents if a not in agent_first_idx]
        missing_required_count = len(missing_required)
        missing_required_penalty = missing_required_count * float(penalties_cfg.get("missing_required_agent", 0.12))

        recovery_penalty = self._compute_recovery_penalty(
            workflow=workflow,
            retries=retries,
            recovery_calls=recovery_calls,
            penalties_cfg=penalties_cfg,
        )

        unnecessary_penalty = unnecessary_calls * float(penalties_cfg.get("unnecessary_repeated_call", 0.02))

        total_penalty = order_penalty + missing_required_penalty + recovery_penalty + unnecessary_penalty
        synthetic_score = max(0.0, min(1.0, task_completion_rate - total_penalty))

        benchmark_success = bool(task_success and synthetic_score >= 0.75)

        retrieve_decisions = [d for d in decisions if d.chosen_action == "retrieve_memory"]
        influence_counts = Counter(
            str((d.memory_influence or {}).get("influence_type") or "none")
            for d in retrieve_decisions
            if (d.memory_influence or {}).get("used") is True
        )

        recovery_success_rate = self._compute_recovery_success_rate(
            workflow=workflow,
            retries=retries,
            recovery_calls=recovery_calls,
            benchmark_success=benchmark_success,
            failed_tasks=failed_tasks,
        )

        scheduling_scores = {
            "agent_assignment_quality": round(assignment_quality, 3),
            "dependency_violation_rate": round(dep_violation_rate, 3),
            "order_violation_rate": round(order_violation_count / max(len(constraints.get("required_order", [])), 1), 3),
            "missing_required_agent_rate": round(missing_required_count / max(len(required_agents), 1), 3),
            "unnecessary_agent_calls": unnecessary_calls,
            "replan_count": replans,
            "retry_count": retries,
            "recovery_success_rate": round(recovery_success_rate, 3),
            "task_completion_rate": round(task_completion_rate, 3),
            "memory_changed_scheduling_decisions": (
                influence_counts.get("changed_agent_selection", 0)
                + influence_counts.get("changed_ordering", 0)
                + influence_counts.get("changed_recovery", 0)
            ),
            "support_only_count": influence_counts.get("support_only", 0),
            "changed_agent_selection_count": influence_counts.get("changed_agent_selection", 0),
            "changed_ordering_count": influence_counts.get("changed_ordering", 0),
            "changed_recovery_count": influence_counts.get("changed_recovery", 0),
        }

        success_factors: list[str] = []
        failure_factors: list[str] = []

        if benchmark_success:
            success_factors.append("benchmark_pass")
        else:
            failure_factors.append("benchmark_below_threshold")

        if dep_violations > 0:
            failure_factors.append("dependency_violations")
        if order_violation_count > 0:
            failure_factors.append("order_violations")
        if missing_required_count > 0:
            failure_factors.append("missing_required_agents")
        if retries > 2:
            failure_factors.append("excessive_retries")

        useful_refs: list[str] = []
        harmful_refs: list[str] = []
        negative_transfer = False
        refs_used = list(memory_refs_used or [])
        if refs_used:
            if benchmark_success:
                useful_refs = refs_used
            else:
                harmful_refs = refs_used
                negative_transfer = True

        decision_evaluations = self._build_decision_evaluations(decisions)

        return SchedulingEvaluation(
            evaluation_id=_uuid(),
            workflow_id=workflow.workflow_id,
            benchmark_success=benchmark_success,
            benchmark_score=round(synthetic_score, 3),
            final_outcome="success" if benchmark_success else "failure",
            scheduling_scores=scheduling_scores,
            decision_evaluations=decision_evaluations,
            success_factors=success_factors,
            failure_factors=failure_factors,
            negative_transfer_detected=negative_transfer,
            memory_used=refs_used,
            useful_memory_refs=useful_refs,
            harmful_memory_refs=harmful_refs,
        )

    def _extract_agent_sequence(self, call_decisions: list[DecisionEvent]) -> list[str]:
        agents: list[str] = []
        for d in call_decisions:
            influence = d.memory_influence or {}
            agent = influence.get("final_agent")
            if isinstance(agent, str) and agent:
                agents.append(agent)
                continue

            rationale = d.rationale_summary or ""
            m = _AGENT_FROM_RATIONALE.search(rationale)
            if m:
                agents.append(m.group(1))
                continue

            if d.chosen_action == "call_recovery_agent":
                agents.append("recovery")
            elif d.chosen_action == "call_agent":
                agents.append("writer")

        return agents

    def _compute_order_penalties(
        self,
        workflow: WorkflowSession,
        decisions: list[DecisionEvent],
        agent_first_idx: dict[str, int],
        constraints: dict[str, Any],
        penalties_cfg: dict[str, Any],
    ) -> tuple[int, float]:
        order_violations = 0
        penalty = 0.0

        for pre, post in constraints.get("required_order", []):
            if pre in agent_first_idx and post in agent_first_idx:
                if agent_first_idx[pre] > agent_first_idx[post]:
                    order_violations += 1
                    penalty += 0.15

        family = workflow.task_family or ""

        writer_idx = agent_first_idx.get("writer")
        researcher_idx = agent_first_idx.get("researcher")
        critic_idx = agent_first_idx.get("critic")

        if writer_idx is not None and researcher_idx is not None and writer_idx < researcher_idx:
            order_violations += 1
            penalty += float(penalties_cfg.get("writer_before_researcher", 0.2))

        if family == "multi_source_conflict" and writer_idx is not None and critic_idx is not None and writer_idx < critic_idx:
            order_violations += 1
            penalty += float(penalties_cfg.get("writer_before_critic", 0.25))

        if family == "form_submission":
            if writer_idx is not None and critic_idx is not None and writer_idx < critic_idx:
                order_violations += 1
                penalty += float(penalties_cfg.get("submit_before_checker", 0.3))

            finalize_idx = self._decision_index(decisions, "finalize")
            if finalize_idx is not None and critic_idx is not None and finalize_idx < critic_idx:
                order_violations += 1
                penalty += float(penalties_cfg.get("finalize_without_verifier", 0.2))

        if family == "debugging" and writer_idx is not None and researcher_idx is not None and writer_idx < researcher_idx:
            order_violations += 1
            penalty += float(penalties_cfg.get("patch_before_reproduce", 0.3))

        return order_violations, penalty

    def _compute_recovery_penalty(
        self,
        workflow: WorkflowSession,
        retries: int,
        recovery_calls: int,
        penalties_cfg: dict[str, Any],
    ) -> float:
        if workflow.task_family != "dynamic_recovery":
            return 0.0

        penalty = 0.0
        if retries >= 2 and recovery_calls == 0:
            penalty += float(penalties_cfg.get("retry_same_failed_strategy", 0.35))
        if recovery_calls == 0:
            penalty += float(penalties_cfg.get("missing_recovery_agent", 0.2))
        return penalty

    def _compute_recovery_success_rate(
        self,
        workflow: WorkflowSession,
        retries: int,
        recovery_calls: int,
        benchmark_success: bool,
        failed_tasks: list[TaskNode],
    ) -> float:
        if workflow.task_family == "dynamic_recovery":
            if retries > 0:
                return 1.0 if recovery_calls > 0 and benchmark_success else 0.0
            return 0.0
        if failed_tasks:
            return 1.0 if recovery_calls > 0 else 0.0
        return 0.0

    @staticmethod
    def _decision_index(decisions: list[DecisionEvent], chosen_action: str) -> int | None:
        for idx, d in enumerate(decisions):
            if d.chosen_action == chosen_action:
                return idx
        return None

    @staticmethod
    def _count_dependency_violations(
        tasks: list[TaskNode],
        decisions: list[DecisionEvent],
    ) -> int:
        """Count agent calls scheduled before task dependencies were called."""
        called_at_step: dict[str, int] = {}
        violations = 0

        for step, d in enumerate(decisions):
            if d.chosen_action in _CALL_ACTIONS and d.task_id:
                called_at_step.setdefault(d.task_id, step)

        for task in tasks:
            if task.task_id not in called_at_step:
                continue
            call_step = called_at_step[task.task_id]
            for dep_id in task.depends_on:
                dep_step = called_at_step.get(dep_id)
                if dep_step is None or dep_step > call_step:
                    violations += 1

        return violations

    @staticmethod
    def _build_decision_evaluations(
        decisions: list[DecisionEvent],
    ) -> list[dict[str, object]]:
        assessments: list[dict[str, object]] = []

        for idx, decision in enumerate(decisions, start=1):
            if decision.chosen_action == "retrieve_memory":
                verdict = "memory_retrieved"
            elif decision.chosen_action in _CALL_ACTIONS and decision.output_refs:
                verdict = "artifact_produced"
            elif decision.chosen_action in _CALL_ACTIONS and not decision.output_refs:
                verdict = "no_artifact"
            else:
                verdict = "control_flow"

            assessments.append(
                {
                    "decision_id": decision.decision_id,
                    "step": idx,
                    "action": decision.chosen_action,
                    "task_id": decision.task_id,
                    "verdict": verdict,
                    "latency_sec": decision.latency_sec,
                    "cost": decision.cost,
                    "memory_ref_count": len(decision.input_memory_refs),
                    "policy_ref_count": len(decision.policy_refs),
                    "output_ref_count": len(decision.output_refs),
                    "memory_influence_type": (decision.memory_influence or {}).get("influence_type"),
                }
            )

        return assessments
