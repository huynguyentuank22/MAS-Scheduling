"""Pydantic schemas for OLM-MAS.

All data contracts for the control plane and data plane.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WorkflowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ArtifactStatus(str, Enum):
    DRAFT = "draft"
    FINAL = "final"
    SUPERSEDED = "superseded"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class CurationAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    IGNORE = "IGNORE"
    DEPRECATE = "DEPRECATE"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Control-plane schemas
# ---------------------------------------------------------------------------

class WorkflowSession(BaseModel):
    """Top-level session representing one benchmark/user episode."""
    workflow_id: str = Field(default_factory=_uuid)
    objective: str = ""
    stakeholder_constraints: dict[str, Any] = Field(default_factory=dict)
    benchmark_name: Optional[str] = None
    task_family: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.CREATED
    created_at: datetime = Field(default_factory=_now)
    updated_at: Optional[datetime] = None
    current_plan_version: int = 1


class TaskNode(BaseModel):
    """A single task in the workflow DAG."""
    task_id: str = Field(default_factory=_uuid)
    workflow_id: str = ""
    parent_id: Optional[str] = None
    description: str = ""
    state: TaskState = TaskState.PENDING
    assigned_agent: Optional[str] = None
    retry_count: int = 0
    checkpoint_ref: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    priority: Optional[float] = None
    risk_score: Optional[float] = None


class AgentProfile(BaseModel):
    """Agent template describing capabilities and constraints."""
    agent_id: str = Field(default_factory=_uuid)
    agent_type: str = ""
    capability_tags: list[str] = Field(default_factory=list)
    tool_endpoint: Optional[str] = None
    allowed_tools: list[str] = Field(default_factory=list)
    disallowed_tools: list[str] = Field(default_factory=list)
    max_parallelism: int = 1
    cost_model: dict[str, Any] = Field(default_factory=dict)
    trust_score: float = 0.5
    health: str = "healthy"
    historical_performance: dict[str, Any] = Field(default_factory=dict)


class PolicyRule(BaseModel):
    """Access-control / constraint rule."""
    rule_id: str = Field(default_factory=_uuid)
    subject_scope: str = "*"          # agent type or "*"
    object_scope: str = "*"           # resource pattern
    action: str = "allow"             # allow / deny
    condition: Optional[str] = None   # optional expression
    transform: Optional[str] = None
    priority: int = 0
    expiry: Optional[datetime] = None
    is_hard_constraint: bool = False


class Artifact(BaseModel):
    """Shared blackboard artifact."""
    artifact_id: str = Field(default_factory=_uuid)
    workflow_id: str = ""
    artifact_type: str = ""           # evidence, draft, critique, plan, etc.
    content_ref: Optional[str] = None
    content: Any = None
    created_by: str = ""
    created_at: datetime = Field(default_factory=_now)
    version: int = 1
    status: ArtifactStatus = ArtifactStatus.DRAFT
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionEvent(BaseModel):
    """Logged every time the scheduler/orchestrator makes a decision."""
    decision_id: str = Field(default_factory=_uuid)
    workflow_id: str = ""
    task_id: Optional[str] = None
    chosen_action: str = ""
    rationale_summary: str = ""
    risk_score: float = 0.0
    human_review_required: bool = False
    input_memory_refs: list[str] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    memory_influence: dict[str, Any] = Field(default_factory=dict)
    cost: Optional[float] = None
    latency_sec: Optional[float] = None
    timestamp: datetime = Field(default_factory=_now)


class ExecutionTraceEvent(BaseModel):
    """Low-level execution event appended to the trace."""
    event_id: str = Field(default_factory=_uuid)
    workflow_id: str = ""
    task_id: Optional[str] = None
    event_type: str = ""
    timestamp: datetime = Field(default_factory=_now)
    actor: str = ""
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SchedulingAction(BaseModel):
    """Output of the Scheduler: what to do next."""
    action_type: str = ""   # spawn_agent, call_agent, replan, retry, finalize, etc.
    agent_template: Optional[str] = None
    task_id: Optional[str] = None
    context_refs: list[str] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    tool_policy: Optional[str] = None
    permission_mode: Optional[str] = None
    rationale: str = ""
    risk_score: float = 0.0
    human_review_required: bool = False
    memory_influence: dict[str, Any] = Field(default_factory=dict)


class SchedulingEvaluation(BaseModel):
    """Post-episode evaluation of scheduling quality."""
    evaluation_id: str = Field(default_factory=_uuid)
    workflow_id: str = ""
    benchmark_success: bool = False
    benchmark_score: float = 0.0
    final_outcome: str = ""
    scheduling_scores: dict[str, float] = Field(default_factory=dict)
    decision_evaluations: list[dict[str, Any]] = Field(default_factory=list)
    success_factors: list[str] = Field(default_factory=list)
    failure_factors: list[str] = Field(default_factory=list)
    negative_transfer_detected: bool = False
    memory_used: list[str] = Field(default_factory=list)
    useful_memory_refs: list[str] = Field(default_factory=list)
    harmful_memory_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class EpisodeReflection(BaseModel):
    """End-of-episode reflection summarizing outcomes."""
    episode_id: str = Field(default_factory=_uuid)
    workflow_id: str = ""
    outcome: str = ""
    root_cause_tags: list[str] = Field(default_factory=list)
    reflection: str = ""
    reward_or_score: float = 0.0
    learned_memory_refs: list[str] = Field(default_factory=list)


class ProceduralControlMemory(BaseModel):
    """Long-term procedural lesson for the orchestrator."""
    memory_id: str = Field(default_factory=_uuid)
    trigger: dict[str, Any] = Field(default_factory=dict)
    recommended_schedule: list[str] = Field(default_factory=list)
    avoid: list[dict[str, Any]] = Field(default_factory=list)
    recommended_recovery: list[dict[str, Any]] = Field(default_factory=list)
    recommended_policy_template: Optional[str] = None
    confidence: float = 0.5
    supporting_episodes: list[str] = Field(default_factory=list)
    negative_cases: list[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=_now)
    status: MemoryStatus = MemoryStatus.ACTIVE
