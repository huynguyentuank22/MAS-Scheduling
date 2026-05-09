# Prompt for Claude Opus in Antigravity

You are working inside this repository. Please implement the MVP described in the project files.

Read these files first, in order:

1. `.antigravity/agent.md`
2. `.antigravity/project.yaml`
3. `docs/requirements.md`
4. `docs/architecture.md`
5. `docs/schemas.md`
6. `docs/implementation_plan.md`
7. `configs/system.yaml`
8. `configs/agents.yaml`
9. `configs/memory_schema.yaml`
10. `configs/experiments.yaml`

Then do the following:

1. Create a Python package under `src/olm_mas/`.
2. Implement Pydantic schemas matching `docs/schemas.md` and `configs/memory_schema.yaml`.
3. Implement an in-memory or SQLite-backed `MemoryStore`.
4. Implement a `Blackboard` artifact store.
5. Implement a basic `PolicyEngine`.
6. Implement a fixed `AgentRegistry` and mock agent runtime.
7. Implement a rule-based `Scheduler` that can optionally retrieve ProceduralControlMemory.
8. Implement the main `Orchestrator` loop.
9. Implement `SchedulingEvaluator` and `MemoryCurator`.
10. Implement a synthetic benchmark runner that generates task episodes with recurring workflow patterns.
11. Add tests for schemas, memory update, scheduling decisions, and ablation runs.
12. Add a CLI command that runs:

```bash
python -m olm_mas.cli run-synthetic --config configs/experiments.yaml
```

Important constraints:

- Keep the code simple and readable.
- Do not add heavy dependencies unless necessary.
- Use JSONL traces for execution logs.
- Every orchestrator action must be logged as a DecisionEvent.
- Do not store raw execution traces as long-term procedural memory. Use evaluator + curator.
- Implement at least two experiment variants: `mas_no_memory` and `mas_orchestrator_memory`.

Before coding, briefly summarize your implementation plan and file tree. Then implement it.
