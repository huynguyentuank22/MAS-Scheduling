# Review Prompt for Claude Opus

Review the current implementation against the requirements.

Check:

1. Are control plane and data plane separated?
2. Are all orchestration decisions logged as DecisionEvent?
3. Is ExecutionTrace append-only JSONL?
4. Does ProceduralControlMemory contain trigger, recommended schedule, avoid patterns, recovery rules, confidence, supporting episodes?
5. Does the scheduler actually use memory in the memory-enabled variant?
6. Does the no-memory variant disable procedural memory retrieval?
7. Does the evaluator produce scheduling-specific metrics, not only task success?
8. Does the curator decide CREATE / UPDATE / IGNORE / DEPRECATE?
9. Are hard PolicyRules protected from automatic modification?
10. Can the synthetic benchmark run end-to-end and produce metrics?

Return:

- issues grouped by severity
- missing requirements
- concrete code changes
- tests to add
