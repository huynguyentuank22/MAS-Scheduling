# Evaluation Plan

## Primary comparison

Compare:

- B1: MAS without orchestrator-local memory
- B2: MAS with orchestrator-local memory

Keep fixed:

- agent templates
- tasks
- tools
- max steps
- scheduler code except memory retrieval/use

## Metrics

### Benchmark metrics

- task success
- official score

### Scheduling metrics

- agent assignment quality
- dependency violation rate
- unnecessary agent calls
- replan count
- retry count
- recovery success rate
- average execution steps

### Memory metrics

- memory hit rate
- useful memory rate
- harmful memory rate
- negative transfer rate
- memory growth rate

### Cost metrics

- LLM calls
- tool calls
- token estimate
- latency

## Synthetic benchmark design

Use recurring task families so memory can accumulate useful lessons:

- evidence-based writing
- web form submission
- debugging workflow

Each family should have:

- hidden ideal schedule
- possible failure modes
- scoring function
- memory-worthy lesson after evaluation

## Evaluation protocol

Offline memory:

1. Run accumulation set.
2. Build memory.
3. Freeze memory.
4. Evaluate on test set.

Online memory:

1. Run tasks sequentially.
2. Update memory after every episode.
3. Plot success/cost over episode index.

## Required report

Produce:

- variant comparison table
- memory growth table
- per-family metrics
- examples of learned procedural memories
- failure case analysis
