"""Rule-based scheduler with optional procedural memory retrieval.

Chooses the next action based on workflow state, pending tasks, and
optionally retrieved ProceduralControlMemory.
"""

from __future__ import annotations

from typing import Any, Optional

from .schemas import (
    ProceduralControlMemory,
    SchedulingAction,
    TaskNode,
    TaskState,
    WorkflowSession,
)
from .agent_registry import AgentRegistry
from .memory_store import MemoryStore


# Mapping from task keywords to preferred agent types
_KEYWORD_AGENT_MAP: dict[str, str] = {
    "plan": "planner",
    "decompose": "planner",
    "research": "researcher",
    "gather": "researcher",
    "evidence": "researcher",
    "browse": "researcher",
    "write": "writer",
    "draft": "writer",
    "synthesize": "writer",
    "execute": "writer",
    "verify": "critic",
    "critique": "critic",
    "check": "critic",
    "review": "critic",
    "recover": "recovery",
    "diagnose": "recovery",
    "retry": "recovery",
    "fix": "recovery",
}

_AVOID_WRITER_BEFORE_CRITIC = "writer_before_critic"
_AVOID_WRITER_BEFORE_EVIDENCE = "writer_before_evidence_complete"
_AVOID_FINALIZE_WITHOUT_VERIFIER = "finalize_without_verifier"
_AVOID_SUBMIT_BEFORE_CHECK = "submit_before_required_field_check"

_CHANGE_ELIGIBILITY_THRESHOLD = 0.7
_SUPPORT_ONLY_THRESHOLD = 0.4


class Scheduler:
    """Rule-based scheduler with optional memory retrieval hook."""

    def __init__(
        self,
        registry: AgentRegistry,
        memory_store: Optional[MemoryStore] = None,
        use_memory: bool = False,
        min_confidence: float = 0.35,
        top_k: int = 3,
    ) -> None:
        self._registry = registry
        self._memory_store = memory_store
        self._use_memory = use_memory
        self._min_confidence = min_confidence
        self._top_k = top_k

    def next_action(
        self,
        workflow: WorkflowSession,
        tasks: list[TaskNode],
    ) -> SchedulingAction:
        """Determine the next scheduling action for the workflow.

        Returns a SchedulingAction describing what to do next.
        """
        memories = self._retrieve_memories(workflow)
        memory_refs = [m.memory_id for m in memories]

        baseline = self._compute_baseline_action(tasks)
        baseline.memory_refs = memory_refs
        baseline_task = self._find_task(tasks, baseline.task_id)

        if memories:
            final_action, influence = self._apply_memory_control(
                workflow=workflow,
                tasks=tasks,
                baseline=baseline,
                baseline_task=baseline_task,
                memories=memories,
            )
            final_action.memory_refs = memory_refs
        else:
            final_action = baseline
            influence = self._default_influence(
                used=False,
                baseline_action=baseline.action_type,
                baseline_agent=baseline.agent_template,
                final_action=baseline.action_type,
                final_agent=baseline.agent_template,
                reason="No memory retrieved",
                memory_id=None,
                influence_type="none",
                trigger_match_score=0.0,
                eligible_to_influence=False,
                blocked_reason=None,
                current_task_family=workflow.task_family,
                memory_task_family=None,
            )

        final_action.memory_influence = influence
        return final_action

    def _retrieve_memories(self, workflow: WorkflowSession) -> list[ProceduralControlMemory]:
        if not (self._use_memory and self._memory_store):
            return []
        return self._memory_store.retrieve_procedural(
            task_family=workflow.task_family,
            min_confidence=self._min_confidence,
            top_k=self._top_k,
        )

    def _compute_baseline_action(self, tasks: list[TaskNode]) -> SchedulingAction:
        """Compute scheduler decision without memory influence."""
        pending = [t for t in tasks if t.state == TaskState.PENDING]
        failed = [t for t in tasks if t.state == TaskState.FAILED]
        running = [t for t in tasks if t.state == TaskState.RUNNING]
        done = [t for t in tasks if t.state == TaskState.DONE]

        # Failed tasks: retry first, then recovery after retry budget is exhausted.
        for task in failed:
            if task.retry_count < 2:
                return SchedulingAction(
                    action_type="retry",
                    agent_template=task.assigned_agent or "recovery",
                    task_id=task.task_id,
                    rationale=f"Retrying failed task (attempt {task.retry_count + 1})",
                    risk_score=0.3,
                )

        for task in failed:
            if task.retry_count >= 2:
                return SchedulingAction(
                    action_type="call_recovery_agent",
                    agent_template="recovery",
                    task_id=task.task_id,
                    rationale="Task exhausted retries, calling recovery agent",
                    risk_score=0.5,
                )

        if not pending and not running:
            return SchedulingAction(
                action_type="finalize",
                rationale="All tasks completed or resolved",
            )

        done_ids = {t.task_id for t in done}
        schedulable = [t for t in pending if all(dep in done_ids for dep in t.depends_on)]

        if not schedulable:
            if running:
                return SchedulingAction(
                    action_type="wait",
                    rationale="Waiting for running tasks to complete dependencies",
                )
            return SchedulingAction(
                action_type="replan",
                rationale="No schedulable tasks and nothing running - potential deadlock",
                risk_score=0.6,
            )

        schedulable.sort(key=lambda t: t.priority or 0.0, reverse=True)
        task = schedulable[0]
        agent_type = self._select_agent_without_memory(task)

        return SchedulingAction(
            action_type="call_agent",
            agent_template=agent_type,
            task_id=task.task_id,
            rationale=f"Scheduling '{task.description}' -> {agent_type}",
        )

    def _apply_memory_control(
        self,
        workflow: WorkflowSession,
        tasks: list[TaskNode],
        baseline: SchedulingAction,
        baseline_task: Optional[TaskNode],
        memories: list[ProceduralControlMemory],
    ) -> tuple[SchedulingAction, dict[str, Any]]:
        """Apply procedural control memories on top of baseline scheduling."""
        assessments = [
            self._assess_memory_eligibility(
                workflow=workflow,
                baseline_task=baseline_task,
                memory=mem,
            )
            for mem in memories
        ]

        support_candidate: Optional[dict[str, Any]] = None
        blocked_candidate: Optional[dict[str, Any]] = None

        for assessment in assessments:
            memory = assessment["memory"]
            proposal = self._propose_memory_action(tasks=tasks, baseline=baseline, memory=memory)
            if not proposal:
                continue

            if proposal["kind"] == "changed":
                if bool(assessment["eligible_to_influence"]):
                    adjusted = proposal["action"]
                    return adjusted, self._build_influence_from_assessment(
                        assessment=assessment,
                        baseline=baseline,
                        final_action=adjusted,
                        influence_type=str(proposal["influence_type"]),
                        reason=str(proposal["reason"]),
                        blocked_reason=None,
                    )

                score = float(assessment["trigger_match_score"])
                if not assessment["blocked_reason"] and score >= _SUPPORT_ONLY_THRESHOLD:
                    if support_candidate is None:
                        support_candidate = self._build_influence_from_assessment(
                            assessment=assessment,
                            baseline=baseline,
                            final_action=baseline,
                            influence_type="support_only",
                            reason=(
                                f"{proposal['reason']} "
                                "(advisory only: trigger_match_below_change_threshold)"
                            ),
                            blocked_reason=None,
                        )
                    continue

                blocked_reason = str(assessment["blocked_reason"] or "trigger_match_below_change_threshold")
                if blocked_candidate is None:
                    blocked_candidate = self._build_influence_from_assessment(
                        assessment=assessment,
                        baseline=baseline,
                        final_action=baseline,
                        influence_type="none",
                        reason=f"{proposal['reason']} (blocked: {blocked_reason})",
                        blocked_reason=blocked_reason,
                    )
                continue

            blocked_reason = assessment["blocked_reason"]
            score = float(assessment["trigger_match_score"])
            if blocked_reason:
                if blocked_candidate is None:
                    blocked_candidate = self._build_influence_from_assessment(
                        assessment=assessment,
                        baseline=baseline,
                        final_action=baseline,
                        influence_type="none",
                        reason=f"{proposal['reason']} (blocked: {blocked_reason})",
                        blocked_reason=str(blocked_reason),
                    )
                continue

            if _SUPPORT_ONLY_THRESHOLD <= score < _CHANGE_ELIGIBILITY_THRESHOLD or bool(
                assessment["eligible_to_influence"]
            ):
                if support_candidate is None:
                    support_candidate = self._build_influence_from_assessment(
                        assessment=assessment,
                        baseline=baseline,
                        final_action=baseline,
                        influence_type="support_only",
                        reason=str(proposal["reason"]),
                        blocked_reason=None,
                    )

        if support_candidate is not None:
            return baseline, support_candidate

        if blocked_candidate is not None:
            return baseline, blocked_candidate

        best = max(assessments, key=lambda a: float(a["trigger_match_score"]))
        best_score = float(best["trigger_match_score"])
        influence_type = "none"
        blocked_reason: str | None = None
        reason = "Memory retrieved but no scheduling control rule matched baseline"
        if best.get("blocked_reason"):
            blocked_reason = str(best["blocked_reason"])
            reason = f"{reason} (blocked: {blocked_reason})"
        elif best_score >= _SUPPORT_ONLY_THRESHOLD:
            influence_type = "support_only"
            reason = "Memory retrieved with moderate-to-strong trigger match; baseline retained"
        else:
            blocked_reason = "trigger_match_below_support_threshold"
            reason = f"{reason} (blocked: {blocked_reason})"

        return baseline, self._build_influence_from_assessment(
            assessment=best,
            baseline=baseline,
            final_action=baseline,
            influence_type=influence_type,
            reason=reason,
            blocked_reason=blocked_reason,
        )

    def _propose_memory_action(
        self,
        tasks: list[TaskNode],
        baseline: SchedulingAction,
        memory: ProceduralControlMemory,
    ) -> Optional[dict[str, Any]]:
        recovery = self._propose_recovery_action(tasks=tasks, baseline=baseline, memory=memory)
        if recovery:
            return recovery

        finalize = self._propose_finalize_action(tasks=tasks, baseline=baseline, memory=memory)
        if finalize:
            return finalize

        return self._propose_agent_and_ordering_action(tasks=tasks, baseline=baseline, memory=memory)

    def _propose_recovery_action(
        self,
        tasks: list[TaskNode],
        baseline: SchedulingAction,
        memory: ProceduralControlMemory,
    ) -> Optional[dict[str, Any]]:
        if baseline.action_type not in {"retry", "call_recovery_agent"}:
            return None

        target = self._find_task(tasks, baseline.task_id)

        for rule in memory.recommended_recovery:
            if not self._recovery_rule_matches(rule, baseline, target):
                continue

            action_name = str(rule.get("action") or rule.get("recommended_action") or "").lower()
            if action_name in {"recovery", "recovery_agent", "call_recovery_agent"}:
                final_action = "call_recovery_agent"
                final_agent = "recovery"
            elif action_name in {"retry"}:
                final_action = "retry"
                final_agent = target.assigned_agent if target and target.assigned_agent else "recovery"
            else:
                continue

            if final_action == baseline.action_type and final_agent == (baseline.agent_template or ""):
                return {
                    "kind": "support",
                    "reason": "Recovery rule matched and supports baseline",
                }

            reason = str(rule.get("reason") or "Recovery rule changed failure handling")
            adjusted = SchedulingAction(
                action_type=final_action,
                agent_template=final_agent,
                task_id=baseline.task_id,
                rationale=reason,
                risk_score=baseline.risk_score,
            )
            return {
                "kind": "changed",
                "action": adjusted,
                "influence_type": "changed_recovery",
                "reason": reason,
            }

        return None

    def _propose_finalize_action(
        self,
        tasks: list[TaskNode],
        baseline: SchedulingAction,
        memory: ProceduralControlMemory,
    ) -> Optional[dict[str, Any]]:
        if baseline.action_type != "finalize":
            return None

        critic_has_run = self._has_agent_run(tasks, "critic")
        avoid_patterns = self._extract_avoid_patterns(memory)
        if (
            _AVOID_FINALIZE_WITHOUT_VERIFIER not in avoid_patterns
            and _AVOID_SUBMIT_BEFORE_CHECK not in avoid_patterns
        ):
            return None

        if critic_has_run:
            return {
                "kind": "support",
                "reason": "Finalize guard matched and verifier prerequisite already satisfied",
            }

        verifier_task = self._pick_verifier_task(tasks)
        if not verifier_task:
            return None

        adjusted = SchedulingAction(
            action_type="call_agent",
            agent_template="critic",
            task_id=verifier_task.task_id,
            rationale="Memory guard prevented finalize before verifier",
            risk_score=baseline.risk_score,
        )
        return {
            "kind": "changed",
            "action": adjusted,
            "influence_type": "changed_ordering",
            "reason": "Finalize deferred until verifier runs",
        }

    def _propose_agent_and_ordering_action(
        self,
        tasks: list[TaskNode],
        baseline: SchedulingAction,
        memory: ProceduralControlMemory,
    ) -> Optional[dict[str, Any]]:
        if baseline.action_type != "call_agent" or not baseline.task_id:
            return None

        baseline_task = self._find_task(tasks, baseline.task_id)
        if not baseline_task:
            return None

        pending = [t for t in tasks if t.state == TaskState.PENDING]
        done_ids = {t.task_id for t in tasks if t.state == TaskState.DONE}
        schedulable = [t for t in pending if all(dep in done_ids for dep in t.depends_on)]

        baseline_agent = baseline.agent_template or self._select_agent_without_memory(baseline_task)

        avoid_patterns = self._extract_avoid_patterns(memory)

        # Guard against unsafe write/finalization sequences.
        unsafe_prereq_agent = self._unsafe_prerequisite_agent(
            baseline_agent=baseline_agent,
            avoid_patterns=avoid_patterns,
            tasks=tasks,
        )
        if unsafe_prereq_agent:
            candidate = self._find_task_for_agent(schedulable, unsafe_prereq_agent)
            chosen_task = candidate or baseline_task
            influence_type = (
                "changed_ordering" if candidate and candidate.task_id != baseline_task.task_id else "changed_agent_selection"
            )
            if unsafe_prereq_agent == baseline_agent and chosen_task.task_id == baseline_task.task_id:
                return {
                    "kind": "support",
                    "reason": "Unsafe-order guard checked and baseline already safe",
                }

            adjusted = SchedulingAction(
                action_type="call_agent",
                agent_template=unsafe_prereq_agent,
                task_id=chosen_task.task_id,
                rationale=f"Memory guard requires {unsafe_prereq_agent} before {baseline_agent}",
                risk_score=baseline.risk_score,
            )
            return {
                "kind": "changed",
                "action": adjusted,
                "influence_type": influence_type,
                "reason": adjusted.rationale,
            }

        # Enforce recommended schedule prerequisites.
        recommended = list(memory.recommended_schedule)
        if baseline_agent in recommended:
            prereqs = [a for a in recommended[:recommended.index(baseline_agent)] if not self._has_agent_run(tasks, a)]
            if prereqs:
                prereq_agent = prereqs[0]
                candidate = self._find_task_for_agent(schedulable, prereq_agent)
                chosen_task = candidate or baseline_task
                influence_type = (
                    "changed_ordering" if candidate and candidate.task_id != baseline_task.task_id else "changed_agent_selection"
                )
                adjusted = SchedulingAction(
                    action_type="call_agent",
                    agent_template=prereq_agent,
                    task_id=chosen_task.task_id,
                    rationale=f"Memory schedule requires {prereq_agent} before {baseline_agent}",
                    risk_score=baseline.risk_score,
                )
                return {
                    "kind": "changed",
                    "action": adjusted,
                    "influence_type": influence_type,
                    "reason": adjusted.rationale,
                }

        # Support marker when memory recommendation agrees with baseline.
        if recommended and baseline_agent in recommended:
            return {
                "kind": "support",
                "reason": "Recommended schedule agrees with baseline agent",
            }

        return None

    def _assess_memory_eligibility(
        self,
        workflow: WorkflowSession,
        baseline_task: Optional[TaskNode],
        memory: ProceduralControlMemory,
    ) -> dict[str, Any]:
        trigger = memory.trigger or {}
        current_task_family = self._normalize_text(workflow.task_family)
        memory_task_family = self._normalize_text(trigger.get("task_family"))
        memory_source_family = self._normalize_text(trigger.get("source_family"))

        score = self._compute_trigger_match_score(
            workflow=workflow,
            baseline_task=baseline_task,
            memory=memory,
        )

        blocked_reason: str | None = None
        if current_task_family and memory_task_family and current_task_family != memory_task_family:
            blocked_reason = "task_family_mismatch"
        elif current_task_family and memory_source_family and current_task_family != memory_source_family:
            blocked_reason = "source_family_mismatch"

        eligible_to_influence = False
        if not blocked_reason:
            eligible_to_influence = score >= _CHANGE_ELIGIBILITY_THRESHOLD
            if score < _SUPPORT_ONLY_THRESHOLD:
                blocked_reason = "trigger_match_below_support_threshold"

        return {
            "memory": memory,
            "trigger_match_score": round(score, 3),
            "eligible_to_influence": eligible_to_influence,
            "blocked_reason": blocked_reason,
            "current_task_family": workflow.task_family,
            "memory_task_family": trigger.get("task_family"),
        }

    def _compute_trigger_match_score(
        self,
        workflow: WorkflowSession,
        baseline_task: Optional[TaskNode],
        memory: ProceduralControlMemory,
    ) -> float:
        trigger = memory.trigger or {}
        score = 0.0

        current_benchmark = self._normalize_text(workflow.benchmark_name)
        memory_benchmark = self._normalize_text(trigger.get("benchmark"))
        if current_benchmark and memory_benchmark and current_benchmark == memory_benchmark:
            score += 0.2

        current_task_family = self._normalize_text(workflow.task_family)
        memory_task_family = self._normalize_text(trigger.get("task_family"))
        if current_task_family and memory_task_family and current_task_family == memory_task_family:
            score += 0.5

        current_pattern = self._current_task_pattern(workflow=workflow, baseline_task=baseline_task)
        memory_pattern = self._normalize_text(trigger.get("task_pattern"))
        if current_pattern and memory_pattern and current_pattern == memory_pattern:
            score += 0.2

        current_constraints = self._extract_constraint_tokens((workflow.stakeholder_constraints or {}).get("constraints"))
        memory_constraints = self._extract_constraint_tokens(trigger.get("constraints"))
        if current_constraints and memory_constraints:
            overlap = len(current_constraints.intersection(memory_constraints)) / float(len(memory_constraints))
            score += min(0.1, overlap * 0.1)

        return min(1.0, max(0.0, score))

    def _build_influence_from_assessment(
        self,
        assessment: dict[str, Any],
        baseline: SchedulingAction,
        final_action: SchedulingAction,
        influence_type: str,
        reason: str,
        blocked_reason: Optional[str],
    ) -> dict[str, Any]:
        memory = assessment["memory"]
        return self._default_influence(
            used=True,
            memory_id=memory.memory_id,
            influence_type=influence_type,
            baseline_action=baseline.action_type,
            baseline_agent=baseline.agent_template,
            final_action=final_action.action_type,
            final_agent=final_action.agent_template,
            reason=reason,
            trigger_match_score=float(assessment["trigger_match_score"]),
            eligible_to_influence=bool(assessment["eligible_to_influence"]),
            blocked_reason=blocked_reason,
            current_task_family=assessment.get("current_task_family"),
            memory_task_family=assessment.get("memory_task_family"),
        )

    def _select_agent_without_memory(self, task: TaskNode) -> str:
        desc_lower = task.description.lower()
        for keyword, agent_type in _KEYWORD_AGENT_MAP.items():
            if keyword in desc_lower and self._registry.get(agent_type):
                return agent_type
        return "writer"

    def _find_task(self, tasks: list[TaskNode], task_id: Optional[str]) -> Optional[TaskNode]:
        if not task_id:
            return None
        return next((t for t in tasks if t.task_id == task_id), None)

    def _find_task_for_agent(self, tasks: list[TaskNode], agent_type: str) -> Optional[TaskNode]:
        for task in sorted(tasks, key=lambda t: t.priority or 0.0, reverse=True):
            if self._select_agent_without_memory(task) == agent_type:
                return task
        return None

    def _pick_verifier_task(self, tasks: list[TaskNode]) -> Optional[TaskNode]:
        pending = [t for t in tasks if t.state == TaskState.PENDING]
        candidate = self._find_task_for_agent(pending, "critic")
        if candidate:
            return candidate
        done = [t for t in tasks if t.state == TaskState.DONE]
        if done:
            return sorted(done, key=lambda t: t.priority or 0.0)[-1]
        return tasks[0] if tasks else None

    def _has_agent_run(self, tasks: list[TaskNode], agent_type: str) -> bool:
        for task in tasks:
            if task.assigned_agent == agent_type and task.state == TaskState.DONE:
                return True
        return False

    def _unsafe_prerequisite_agent(
        self,
        baseline_agent: str,
        avoid_patterns: set[str],
        tasks: list[TaskNode],
    ) -> str | None:
        if baseline_agent != "writer":
            return None

        if _AVOID_WRITER_BEFORE_CRITIC in avoid_patterns and not self._has_agent_run(tasks, "critic"):
            return "critic"

        if _AVOID_WRITER_BEFORE_EVIDENCE in avoid_patterns and not self._has_agent_run(tasks, "researcher"):
            return "researcher"

        if _AVOID_SUBMIT_BEFORE_CHECK in avoid_patterns and not self._has_agent_run(tasks, "critic"):
            return "critic"

        return None

    @staticmethod
    def _normalize_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip().lower()
        return text or None

    def _current_task_pattern(
        self,
        workflow: WorkflowSession,
        baseline_task: Optional[TaskNode],
    ) -> str | None:
        constraints = workflow.stakeholder_constraints or {}
        pattern = constraints.get("task_pattern") or constraints.get("pattern")
        normalized = self._normalize_text(pattern)
        if normalized:
            return normalized
        if baseline_task is not None:
            return self._normalize_text(baseline_task.description)
        return None

    def _extract_constraint_tokens(self, value: Any) -> set[str]:
        out: set[str] = set()
        if value is None:
            return out
        if isinstance(value, str):
            normalized = self._normalize_text(value)
            if normalized:
                out.add(normalized)
            return out
        if isinstance(value, (list, tuple, set)):
            for item in value:
                out.update(self._extract_constraint_tokens(item))
            return out
        if isinstance(value, dict):
            for key, item in value.items():
                norm_key = self._normalize_text(key)
                if norm_key:
                    out.add(norm_key)
                out.update(self._extract_constraint_tokens(item))
            return out
        return out

    def _extract_avoid_patterns(self, memory: ProceduralControlMemory) -> set[str]:
        patterns: set[str] = set()
        for item in memory.avoid:
            if isinstance(item, str):
                patterns.add(item)
                continue
            action = item.get("action")
            if isinstance(action, str):
                patterns.add(action)
            pattern = item.get("pattern")
            if isinstance(pattern, str):
                patterns.add(pattern)
        return patterns

    def _recovery_rule_matches(
        self,
        rule: dict[str, Any],
        baseline: SchedulingAction,
        target_task: Optional[TaskNode],
    ) -> bool:
        when_action = str(rule.get("when_action") or rule.get("on_action") or "").strip()
        if when_action and when_action != baseline.action_type:
            return False

        if target_task is not None:
            retry_count = target_task.retry_count
            exact_retry = rule.get("retry_count")
            if isinstance(exact_retry, int) and retry_count != exact_retry:
                return False

            min_retry = rule.get("min_retry_count")
            if isinstance(min_retry, int) and retry_count < min_retry:
                return False

            max_retry = rule.get("max_retry_count")
            if isinstance(max_retry, int) and retry_count > max_retry:
                return False

        return True

    @staticmethod
    def _default_influence(
        used: bool,
        baseline_action: str,
        baseline_agent: Optional[str],
        final_action: str,
        final_agent: Optional[str],
        reason: str,
        memory_id: Optional[str] = None,
        influence_type: str = "none",
        trigger_match_score: float = 0.0,
        eligible_to_influence: bool = False,
        blocked_reason: Optional[str] = None,
        current_task_family: Optional[str] = None,
        memory_task_family: Optional[str] = None,
    ) -> dict[str, Any]:
        return {
            "used": used,
            "memory_id": memory_id,
            "influence_type": influence_type,
            "baseline_action": baseline_action,
            "baseline_agent": baseline_agent,
            "final_action": final_action,
            "final_agent": final_agent,
            "reason": reason,
            "trigger_match_score": trigger_match_score,
            "eligible_to_influence": eligible_to_influence,
            "blocked_reason": blocked_reason,
            "current_task_family": current_task_family,
            "memory_task_family": memory_task_family,
        }
