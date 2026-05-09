# Antigravity Coding Pack: Orchestrator-Local Memory for MAS

This pack gives a coding agent enough structure to implement a prototype for **orchestrator-local memory in multi-agent systems**.

Use it in Antigravity by placing this folder at the root of your project and asking Claude Opus to read:

1. `.antigravity/agent.md`
2. `.antigravity/project.yaml`
3. `docs/requirements.md`
4. `docs/architecture.md`
5. `docs/implementation_plan.md`
6. `configs/system.yaml`

Recommended first prompt is in:

```text
.antigravity/prompts/claude_opus_start.md
```

## Intended MVP

The MVP should implement:

- Orchestrator runtime
- Agent templates and agent runtime
- Local memory store
- Shared blackboard/artifact store
- Policy engine
- Trace logger
- Scheduling evaluator
- Memory curator
- Synthetic benchmark runner
- Ablation: no memory vs orchestrator-local memory

## Project convention

The coding agent should treat `.antigravity/project.yaml` as the top-level source of truth and use `configs/*.yaml` for implementation constants.
