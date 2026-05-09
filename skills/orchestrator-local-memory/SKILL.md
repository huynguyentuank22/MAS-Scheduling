---
name: orchestrator-local-memory
compact: false
description: Use this when coding, reviewing, or extending the Orchestrator-Local Memory for Multi-Agent Systems prototype. It guides implementation of the orchestrator runtime, local control memory schema, blackboard/artifact store, policy engine, scheduler, trace logger, post-task scheduling evaluator, memory curator, benchmark adapters, and ablation experiments.
---

# Orchestrator-Local Memory Coding Skill

## Purpose

Help implement a research MVP where a multi-agent orchestrator uses local control memory to improve scheduling, delegation, context selection, access control, recovery, and adaptation across task episodes.

## Core design rule

Always separate:

- **Control plane**: orchestrator-local memory, scheduling state, policies, decisions, traces, evaluations, procedural control memories.
- **Data plane**: shared blackboard/artifact store, evidence, drafts, critiques, tool outputs, checkpoints.

## Required behavior when coding

1. Read `.antigravity/project.yaml` and `configs/system.yaml` first.
2. Use `docs/requirements.md` and `docs/schemas.md` as source of truth.
3. Implement schemas before runtime logic.
4. Ensure every orchestrator scheduling action is logged as a `DecisionEvent`.
5. Store execution traces as append-only JSONL.
6. Do not store raw traces directly as long-term procedural memory.
7. Use `SchedulingEvaluator` and `MemoryCurator` before updating procedural memory.
8. Keep hard policy rules separate from learned policy-selection memories.
9. Support at least two variants: no-memory MAS and orchestrator-memory MAS.
10. Add tests for every module before expanding complexity.

## MVP module order

1. `schemas.py`
2. `memory_store.py`
3. `blackboard.py`
4. `policy_engine.py`
5. `agent_registry.py`
6. `agent_runtime.py`
7. `scheduler.py`
8. `trace_logger.py`
9. `orchestrator.py`
10. `evaluator.py`
11. `memory_curator.py`
12. `benchmark_runner.py`
13. `cli.py`

## Avoid

- Do not create benchmark-specific agent teams as the main design.
- Do not let orchestrator rewrite hard safety policy automatically.
- Do not mix artifact store content with procedural control memory.
- Do not evaluate only final task success; scheduling metrics are required.
- Do not add RL or distributed execution in the MVP.
