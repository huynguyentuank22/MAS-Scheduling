# Schemas

Implement these as Pydantic models or dataclasses. Prefer Pydantic for MVP.

## WorkflowSession

Fields: workflow_id, objective, stakeholder_constraints, benchmark_name, task_family, status, created_at, updated_at, current_plan_version.

## TaskNode

Fields: task_id, workflow_id, parent_id, description, state, assigned_agent, retry_count, checkpoint_ref, depends_on, priority, risk_score.

## AgentProfile

Fields: agent_id, agent_type, capability_tags, tool_endpoint, allowed_tools, disallowed_tools, max_parallelism, cost_model, trust_score, health, historical_performance.

## PolicyRule

Fields: rule_id, subject_scope, object_scope, action, condition, transform, priority, expiry, is_hard_constraint.

## Artifact

Fields: artifact_id, workflow_id, artifact_type, content_ref, content, created_by, created_at, version, status, metadata.

## DecisionEvent

Fields: decision_id, workflow_id, task_id, chosen_action, rationale_summary, risk_score, human_review_required, input_memory_refs, policy_refs, output_refs, cost, latency_sec, timestamp.

## ExecutionTraceEvent

Fields: event_id, workflow_id, task_id, event_type, timestamp, actor, input_refs, output_refs, metadata.

## SchedulingAction

Fields: action_type, agent_template, task_id, context_refs, memory_refs, artifact_refs, tool_policy, permission_mode, rationale, risk_score, human_review_required.

## SchedulingEvaluation

Fields: evaluation_id, workflow_id, benchmark_success, benchmark_score, final_outcome, scheduling_scores, decision_evaluations, success_factors, failure_factors, negative_transfer_detected, memory_used, useful_memory_refs, harmful_memory_refs, created_at.

## EpisodeReflection

Fields: episode_id, workflow_id, outcome, root_cause_tags, reflection, reward_or_score, learned_memory_refs.

## ProceduralControlMemory

Fields: memory_id, trigger, recommended_schedule, avoid, recommended_recovery, recommended_policy_template, confidence, supporting_episodes, negative_cases, last_updated, status.
