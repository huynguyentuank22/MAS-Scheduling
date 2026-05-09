# Agent Instructions for Antigravity / Claude Opus

You are coding a research MVP for **Orchestrator-Local Memory for Multi-Agent Systems**.

## Core idea

The system treats every benchmark/user task as an episode. During an episode, the orchestrator schedules agents, mediates access to memory/blackboard/tools, logs all decisions, and produces artifacts. After the episode, the system evaluates scheduling quality and curates lessons into procedural control memory. Future episodes retrieve those memories to improve scheduling.

## Most important design rule

Separate:

- **Control plane**: orchestrator-local memory, scheduling decisions, policies, traces, evaluations, procedural lessons.
- **Data plane**: shared blackboard/artifact store, evidence, drafts, critiques, tool outputs, final outputs.

Do not mix raw artifacts with long-term procedural memory.

## Implementation priorities

1. Implement schemas first.
2. Implement storage and trace logging second.
3. Implement blackboard and policy engine third.
4. Implement agent registry and mock/LLM agent runtime fourth.
5. Implement scheduler and orchestrator loop fifth.
6. Implement evaluator and memory curator sixth.
7. Implement synthetic benchmark runner and ablations last.

## MVP constraints

- Use fixed reusable agent templates: Planner, Researcher, Writer, Critic/Verifier, Recovery Agent.
- Do not create benchmark-specific agent roles as the main system design.
- Scheduler may be rule-based for MVP, but it must expose hooks for memory retrieval.
- Every scheduling decision must become a DecisionEvent.
- Execution traces must be append-only JSONL.
- ProceduralControlMemory must include trigger conditions and confidence.
- Policy hard constraints must not be silently modified by the orchestrator.

## Definition of done

The MVP is done when the project can run a synthetic benchmark with two variants:

- MAS without orchestrator memory
- MAS with orchestrator-local memory

and produce:

- per-episode traces
- benchmark success metrics
- scheduling evaluation metrics
- procedural memory updates
- a comparison report
