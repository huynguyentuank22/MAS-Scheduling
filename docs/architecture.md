# Architecture

## Conceptual split

The system separates two planes.

### Control plane

Managed by the Orchestrator Runtime:

- WorkflowSession
- TaskNode / Plan
- AgentRegistry
- PolicyRule
- Delegation / Spawn Memory
- DecisionEvent
- ExecutionTrace
- SchedulingEvaluation
- EpisodeReflection
- ProceduralControlMemory

This plane answers: **what should the orchestrator do next?**

### Data plane

Managed by the Shared Blackboard / Artifact Store:

- evidence
- drafts
- critiques
- tool outputs
- checkpoints
- final outputs

This plane answers: **what shared artifacts do agents need to collaborate?**

## Runtime modules

- `Orchestrator`: main episode loop.
- `Scheduler`: chooses next action.
- `PolicyEngine`: creates allowed memory/artifact/tool view for each agent call.
- `AgentRegistry`: stores templates and performance profiles.
- `AgentRuntime`: calls/spawns agents.
- `Blackboard`: stores artifacts.
- `TraceLogger`: writes DecisionEvent and trace events.
- `SchedulingEvaluator`: evaluates scheduling quality after task.
- `MemoryCurator`: extracts procedural control memory.
- `MemoryStore`: persists local memory entities.

## Main flow

```text
Task → WorkflowSession → Retrieve Memory → Schedule → Call Agent → Blackboard Artifact
     → Trace → Benchmark Evaluation → Scheduling Evaluation → Memory Curation
     → Procedural Control Memory → Future Task
```

## Decision types

Scheduler may output:

- `retrieve_memory`
- `spawn_agent`
- `call_agent`
- `replan`
- `retry`
- `call_verifier`
- `call_recovery_agent`
- `write_blackboard`
- `finalize`
- `ask_human`

Every decision must be logged as a `DecisionEvent`.
