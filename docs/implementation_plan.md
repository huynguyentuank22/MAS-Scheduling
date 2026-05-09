# Implementation Plan

## Phase 1: Project skeleton

Create:

```text
src/olm_mas/
  __init__.py
  schemas.py
  memory_store.py
  blackboard.py
  agent_registry.py
  agent_runtime.py
  policy_engine.py
  scheduler.py
  trace_logger.py
  evaluator.py
  memory_curator.py
  benchmark_runner.py
  cli.py

tests/
  test_schemas.py
  test_memory_store.py
  test_blackboard.py
  test_scheduler.py
  test_memory_update.py
  test_synthetic_run.py
```

## Phase 2: Schemas and stores

Implement schemas first. Then implement:

- in-memory store for unit tests;
- optional SQLite persistence;
- JSONL trace writer;
- filesystem artifact store.

## Phase 3: Agent runtime

Implement mock agents first. Each agent should return structured output. Later replace with LLM-backed agents.

## Phase 4: Scheduler

Implement rule-based scheduler:

- identify next pending TaskNode;
- retrieve relevant ProceduralControlMemory if enabled;
- choose agent based on task description and memory suggestions;
- emit SchedulingAction.

## Phase 5: Orchestrator loop

Implement episode loop:

- create workflow;
- create initial task;
- retrieve memory;
- schedule;
- log decision;
- enforce policy;
- run agent;
- write artifact;
- update task state;
- stop when finalized.

## Phase 6: Evaluator and curator

Evaluator produces scheduling scorecard. Curator extracts lessons and decides CREATE / UPDATE / IGNORE / DEPRECATE.

## Phase 7: Synthetic benchmark and ablation

Generate recurring task families with hidden good schedules and failure modes. Run:

- `mas_no_memory`
- `mas_orchestrator_memory`

Produce metrics JSON/CSV.
