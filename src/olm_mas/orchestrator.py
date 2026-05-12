"""Orchestrator - main episode loop.

Runs a single episode: creates a workflow session, schedules agents,
logs decisions, enforces policies, and produces artifacts.
"""

from __future__ import annotations

from typing import Any, Optional

from .schemas import (
    AgentProfile,
    AgentOutput,
    AgentOutputStatus,
    CurationAction,
    DecisionEvent,
    EpisodeReflection,
    ExecutionTraceEvent,
    TaskNode,
    TaskState,
    WorkflowSession,
    WorkflowStatus,
    _now,
)
from .agent_registry import AgentRegistry
from .agent_runtime import AgentRuntime
from .blackboard import Blackboard
from .evaluator import SchedulingEvaluator
from .memory_curator import MemoryCurator
from .memory_store import MemoryStore
from .policy_engine import PolicyEngine
from .scheduler import Scheduler
from .trace_logger import TraceLogger


class Orchestrator:
    """Runs one complete episode from task to evaluation."""

    def __init__(
        self,
        registry: AgentRegistry,
        runtime: AgentRuntime,
        memory_store: MemoryStore,
        blackboard: Blackboard,
        policy_engine: PolicyEngine,
        trace_logger: TraceLogger,
        evaluator: SchedulingEvaluator,
        curator: Optional[MemoryCurator] = None,
        use_memory: bool = False,
        max_steps: int = 30,
        min_confidence: float = 0.35,
        top_k: int = 3,
    ) -> None:
        self._registry = registry
        self._runtime = runtime
        self._store = memory_store
        self._blackboard = blackboard
        self._policy = policy_engine
        self._trace = trace_logger
        self._evaluator = evaluator
        self._curator = curator
        self._use_memory = use_memory
        self._max_steps = max_steps

        self._scheduler = Scheduler(
            registry=registry,
            memory_store=memory_store if use_memory else None,
            use_memory=use_memory,
            min_confidence=min_confidence,
            top_k=top_k,
        )

    def run_episode(
        self,
        objective: str,
        task_descriptions: list[str],
        benchmark_name: str = "synthetic",
        task_family: str | None = None,
        expected_success: bool = True,
    ) -> dict[str, Any]:
        """Run a single benchmark episode.

        Args:
            objective: High-level goal description.
            task_descriptions: List of sub-task descriptions.
            benchmark_name: Name of the benchmark suite.
            task_family: Task category for memory retrieval.
            expected_success: Ground truth for evaluation.

        Returns:
            dict with workflow, decisions, evaluation, curation_actions.
        """
        # Isolate artifacts across episodes.
        self._blackboard.clear()

        # 1. Create workflow session
        workflow = WorkflowSession(
            objective=objective,
            benchmark_name=benchmark_name,
            task_family=task_family,
            status=WorkflowStatus.RUNNING,
        )
        self._store.put_workflow(workflow)

        # 2. Create task nodes
        tasks: list[TaskNode] = []
        prev_id: str | None = None
        for i, desc in enumerate(task_descriptions):
            task = TaskNode(
                workflow_id=workflow.workflow_id,
                description=desc,
                depends_on=[prev_id] if prev_id else [],
                priority=float(len(task_descriptions) - i),
            )
            tasks.append(task)
            self._store.put_task(task)
            prev_id = task.task_id

        # 3. Episode loop
        decisions: list[DecisionEvent] = []
        memory_refs_used: list[str] = []
        episode_agent_stats: dict[str, dict[str, float]] = {}
        output_validation_stats: dict[str, float] = {
            "agent_calls": 0.0,
            "schema_valid_calls": 0.0,
            "parse_failures": 0.0,
            "repair_attempts": 0.0,
            "repair_successes": 0.0,
            "invalid_artifact_refs": 0.0,
            "invalid_outputs": 0.0,
        }
        step = 0

        def _record_decision(event: DecisionEvent) -> None:
            self._store.put_decision(event)
            self._trace.log_decision(event)

        while step < self._max_steps:
            step += 1

            # Schedule next action
            action = self._scheduler.next_action(workflow, tasks)

            # Emit explicit memory retrieval decision whenever scheduler used memory.
            if self._use_memory and action.memory_refs:
                influence = dict(action.memory_influence or {})
                influence_type = str(influence.get("influence_type") or "none")
                retrieve_event = DecisionEvent(
                    workflow_id=workflow.workflow_id,
                    task_id=action.task_id,
                    chosen_action="retrieve_memory",
                    rationale_summary=(
                        f"Retrieved {len(action.memory_refs)} procedural memories "
                        f"for scheduling ({influence_type})"
                    ),
                    input_memory_refs=action.memory_refs,
                    memory_influence=influence,
                    timestamp=_now(),
                )
                decisions.append(retrieve_event)
                _record_decision(retrieve_event)

            # Log scheduler decision
            decision = DecisionEvent(
                workflow_id=workflow.workflow_id,
                task_id=action.task_id,
                chosen_action=action.action_type,
                rationale_summary=action.rationale,
                risk_score=action.risk_score,
                input_memory_refs=action.memory_refs,
                memory_influence=dict(action.memory_influence or {}),
                timestamp=_now(),
            )
            decisions.append(decision)

            # Track memory refs
            memory_refs_used.extend(action.memory_refs)

            # Handle finalize
            if action.action_type == "finalize":
                _record_decision(decision)
                break

            # Handle wait (skip step)
            if action.action_type == "wait":
                # In mock mode, complete any running tasks
                for t in tasks:
                    if t.state == TaskState.RUNNING:
                        t.state = TaskState.DONE
                        self._store.put_task(t)
                _record_decision(decision)
                continue

            # Handle replan
            if action.action_type == "replan":
                # Simple replan: unblock one stuck task
                for t in tasks:
                    if t.state == TaskState.PENDING:
                        t.depends_on = []
                        self._store.put_task(t)
                        break
                _record_decision(decision)
                continue

            # Find the target task
            target_task: Optional[TaskNode] = None
            if action.task_id:
                target_task = next((t for t in tasks if t.task_id == action.task_id), None)

            if not target_task:
                _record_decision(decision)
                continue

            # Handle retry
            if action.action_type == "retry":
                target_task.state = TaskState.PENDING
                target_task.retry_count += 1
                self._store.put_task(target_task)
                _record_decision(decision)
                continue

            # Enforce policy
            agent_type = action.agent_template or "writer"
            allowed, reason, rule_ids = self._policy.check(agent_type, "execute_task")
            decision.policy_refs = rule_ids
            if not allowed:
                _record_decision(decision)
                # Log policy denial
                self._trace.log_trace(
                    ExecutionTraceEvent(
                        workflow_id=workflow.workflow_id,
                        task_id=target_task.task_id,
                        event_type="policy_denied",
                        actor="policy_engine",
                        metadata={"reason": reason},
                    )
                )
                continue

            # Get agent profile
            profile = self._registry.get(agent_type)
            if not profile:
                profile = self._registry.get("writer")
            if not profile:
                _record_decision(decision)
                continue

            # Run agent
            target_task.state = TaskState.RUNNING
            target_task.assigned_agent = agent_type
            self._store.put_task(target_task)

            # Compute quality boost from memory
            quality_boost = 0.0
            if self._use_memory and action.memory_refs:
                quality_boost = 0.05 * len(action.memory_refs)

            result = self._runtime.run(
                profile=profile,
                task_description=target_task.description,
                quality_boost=quality_boost,
            )
            agent_output = result.get("agent_output")
            if not isinstance(agent_output, AgentOutput):
                agent_output = AgentOutput(
                    status=AgentOutputStatus.INVALID,
                    summary="Runtime returned non-AgentOutput payload",
                    artifact_type="invalid_output",
                    artifact_payload={},
                    confidence=0.0,
                    uncertainties=[],
                    schema_valid=False,
                    validation_errors=["runtime_payload_missing_agent_output"],
                )
            parse_meta = dict(result.get("parse_meta") or {})

            # Populate decision metrics after call
            decision.latency_sec = float(result.get("latency_sec", 0.0))
            decision.cost = self._estimate_cost(profile)

            output_validation_stats["agent_calls"] += 1.0
            if agent_output.schema_valid:
                output_validation_stats["schema_valid_calls"] += 1.0
            else:
                output_validation_stats["invalid_outputs"] += 1.0
            if bool(parse_meta.get("parse_failed", False)):
                output_validation_stats["parse_failures"] += 1.0
            if bool(parse_meta.get("repair_attempted", False)):
                output_validation_stats["repair_attempts"] += 1.0
            if bool(parse_meta.get("repair_succeeded", False)):
                output_validation_stats["repair_successes"] += 1.0
            invalid_fields = set(parse_meta.get("invalid_runtime_fields") or [])
            if "artifact_id" in invalid_fields:
                output_validation_stats["invalid_artifact_refs"] += 1.0

            runtime_success = bool(
                agent_output.schema_valid
                and agent_output.status in {AgentOutputStatus.SUCCESS, AgentOutputStatus.PARTIAL_SUCCESS}
            )
            self._update_episode_agent_stats(
                episode_agent_stats,
                agent_type=agent_type,
                success=runtime_success,
                latency_sec=decision.latency_sec,
                cost=decision.cost,
            )

            # Log execution trace
            self._trace.log_trace(
                ExecutionTraceEvent(
                    workflow_id=workflow.workflow_id,
                    task_id=target_task.task_id,
                    event_type="agent_call",
                    actor=agent_type,
                    metadata={
                        "success": runtime_success,
                        "latency_sec": decision.latency_sec,
                        "schema_valid": agent_output.schema_valid,
                        "agent_output_status": agent_output.status.value,
                        "raw_output_ref": agent_output.raw_output_ref,
                    },
                )
            )

            if not agent_output.schema_valid:
                self._trace.log_trace(
                    ExecutionTraceEvent(
                        workflow_id=workflow.workflow_id,
                        task_id=target_task.task_id,
                        event_type="invalid_agent_output",
                        actor=agent_type,
                        metadata={
                            "raw_output_ref": agent_output.raw_output_ref,
                            "validation_errors": list(agent_output.validation_errors),
                            "repair_attempt_count": agent_output.repair_attempt_count,
                            "parse_meta": parse_meta,
                        },
                    )
                )

            if runtime_success:
                # Write artifact to blackboard
                artifact = self._blackboard.write(
                    workflow_id=workflow.workflow_id,
                    artifact_type=agent_output.artifact_type,
                    content=agent_output.artifact_payload,
                    created_by=agent_type,
                )
                decision.output_refs = [artifact.artifact_id]
                target_task.state = TaskState.DONE
            else:
                target_task.state = TaskState.FAILED

            self._store.put_task(target_task)
            _record_decision(decision)

        # 4. Finalize workflow
        all_done = all(t.state == TaskState.DONE for t in tasks)
        workflow.status = WorkflowStatus.COMPLETED if all_done else WorkflowStatus.FAILED
        workflow.updated_at = _now()
        self._store.put_workflow(workflow)

        # 5. Evaluate
        task_success = all_done
        benchmark_score = 1.0 if task_success else 0.0
        unique_memory_refs = list(set(memory_refs_used))

        evaluation = self._evaluator.evaluate(
            workflow=workflow,
            tasks=tasks,
            decisions=decisions,
            task_success=task_success,
            benchmark_score=benchmark_score,
            memory_refs_used=unique_memory_refs,
        )

        # Attach LLM-readiness validation metrics to scheduling scores.
        agent_calls = max(output_validation_stats["agent_calls"], 1.0)
        repair_attempts = max(output_validation_stats["repair_attempts"], 1.0)
        evaluation.scheduling_scores["agent_output_schema_valid_rate"] = round(
            output_validation_stats["schema_valid_calls"] / agent_calls,
            3,
        )
        evaluation.scheduling_scores["parse_failure_rate"] = round(
            output_validation_stats["parse_failures"] / agent_calls,
            3,
        )
        evaluation.scheduling_scores["repair_success_rate"] = round(
            output_validation_stats["repair_successes"] / repair_attempts,
            3,
        )
        evaluation.scheduling_scores["invalid_artifact_ref_rate"] = round(
            output_validation_stats["invalid_artifact_refs"] / agent_calls,
            3,
        )

        if output_validation_stats["invalid_outputs"] > 0:
            if "invalid_agent_output" not in evaluation.failure_factors:
                evaluation.failure_factors.append("invalid_agent_output")

        self._store.put_evaluation(evaluation)

        # 6. Curate memory
        curation_actions: list[dict[str, Any]] = []
        if self._curator:
            curation_actions = self._curator.curate(
                workflow=workflow,
                evaluation=evaluation,
                decisions=decisions,
            )

        total_curation = max(len(curation_actions), 1)
        accepted_count = sum(1 for item in curation_actions if bool(item.get("accepted")))
        rejected_count = len(curation_actions) - accepted_count
        validation_failures = sum(
            1
            for item in curation_actions
            if str(item.get("reason", "")).startswith("validation_failed:")
        )
        unsupported_lesson_count = sum(
            1
            for item in curation_actions
            if "unsupported" in str(item.get("reason", ""))
        )
        overgeneralized_count = sum(
            1
            for item in curation_actions
            if "overgeneralized" in str(item.get("reason", ""))
        )

        evaluation.scheduling_scores["memory_validation_failure_rate"] = round(
            validation_failures / total_curation,
            3,
        )
        evaluation.scheduling_scores["unsupported_lesson_rate"] = round(
            unsupported_lesson_count / total_curation,
            3,
        )
        evaluation.scheduling_scores["overgeneralized_memory_rate"] = round(
            overgeneralized_count / total_curation,
            3,
        )
        evaluation.scheduling_scores["curator_accept_rate"] = round(
            accepted_count / total_curation,
            3,
        )
        evaluation.scheduling_scores["curator_reject_rate"] = round(
            rejected_count / total_curation,
            3,
        )
        self._store.put_evaluation(evaluation)

        # 7. Create and store episode reflection
        learned_memory_refs = [
            str(item.get("memory_id"))
            for item in curation_actions
            if item.get("memory_id")
            and bool(item.get("accepted"))
            and (
                item.get("action") in {CurationAction.CREATE, CurationAction.UPDATE}
                or str(item.get("action")) in {CurationAction.CREATE.value, CurationAction.UPDATE.value}
            )
        ]
        root_cause_tags = evaluation.failure_factors or evaluation.success_factors
        reflection = EpisodeReflection(
            workflow_id=workflow.workflow_id,
            outcome=evaluation.final_outcome,
            root_cause_tags=root_cause_tags,
            reflection=(
                f"Episode {evaluation.final_outcome} after {len(decisions)} decisions; "
                f"completion={evaluation.scheduling_scores.get('task_completion_rate', 0.0)}"
            ),
            reward_or_score=evaluation.benchmark_score,
            learned_memory_refs=learned_memory_refs,
        )
        self._store.put_reflection(reflection)

        # 8. Update registry historical performance after each episode
        self._registry.update_historical_performance(
            episode_agent_stats=episode_agent_stats,
            workflow_id=workflow.workflow_id,
            episode_outcome=evaluation.final_outcome,
        )

        return {
            "workflow": workflow,
            "tasks": tasks,
            "decisions": decisions,
            "evaluation": evaluation,
            "curation_actions": curation_actions,
            "memory_refs_used": unique_memory_refs,
            "reflection": reflection,
        }

    @staticmethod
    def _estimate_cost(profile: AgentProfile) -> float:
        """Convert profile cost model into a numeric scalar for DecisionEvent.cost."""
        model = profile.cost_model or {}

        explicit = model.get("relative_cost_value")
        if isinstance(explicit, (int, float)):
            return float(explicit)

        absolute = model.get("cost")
        if isinstance(absolute, (int, float)):
            return float(absolute)

        relative = model.get("relative_cost")
        if isinstance(relative, str):
            mapping = {
                "low": 0.5,
                "medium": 1.0,
                "high": 1.5,
            }
            return float(mapping.get(relative.lower(), 1.0))

        return 0.0

    @staticmethod
    def _update_episode_agent_stats(
        episode_agent_stats: dict[str, dict[str, float]],
        agent_type: str,
        success: bool,
        latency_sec: float,
        cost: float,
    ) -> None:
        stats = episode_agent_stats.setdefault(
            agent_type,
            {
                "calls": 0.0,
                "success_calls": 0.0,
                "failure_calls": 0.0,
                "total_latency_sec": 0.0,
                "total_cost": 0.0,
            },
        )
        stats["calls"] += 1.0
        if success:
            stats["success_calls"] += 1.0
        else:
            stats["failure_calls"] += 1.0
        stats["total_latency_sec"] += float(latency_sec)
        stats["total_cost"] += float(cost)
