# Requirements Summary

Build a research MVP for **orchestrator-local memory in multi-agent systems**.

## Core requirement

Every benchmark/user task is an episode. The orchestrator must:

1. receive the task;
2. create a WorkflowSession;
3. retrieve relevant local procedural memories;
4. plan/schedule agents;
5. call or spawn agents with scoped context, memory, tools, and permissions;
6. write artifacts to the shared blackboard;
7. log every scheduling decision;
8. evaluate official task outcome;
9. evaluate scheduling quality;
10. curate lessons into procedural control memory;
11. reuse memories for future episodes.

## Must-have MVP features

- Fixed reusable agent templates.
- Rule-based scheduler with memory retrieval hook.
- Orchestrator-local memory store.
- Shared blackboard/artifact store.
- Policy engine for read/write/tool permissions.
- Append-only JSONL execution trace.
- Scheduling evaluator.
- Memory curator supporting CREATE / UPDATE / IGNORE / DEPRECATE.
- Synthetic benchmark runner.
- Ablation: no memory vs orchestrator-local memory.

## Core hypothesis

Orchestrator-local memory improves multi-agent scheduling by maintaining persistent control state over task decomposition, agent capability, delegation history, memory access policy, execution trace, and recovery experience.

## Non-goals

- No distributed execution in MVP.
- No full RL scheduler in MVP.
- No full UI dashboard in MVP.
- No automatic modification of hard safety policies.
- No benchmark-specific hard-coded agent team as the main design.
