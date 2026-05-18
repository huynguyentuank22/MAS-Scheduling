# Validation Metrics Report

| Variant | success rate | mean score | final answer present rate | final answer schema valid rate | final answer missing due to setup error rate | answer normalized match rate | agent output schema valid rate | agent task success rate | agent failed status rate | llm setup error rate | parse failure rate | repair success rate | invalid artifact ref rate | memory validation failure rate | unsupported lesson rate | overgeneralized memory rate | curator accept rate | curator reject rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mas_orchestrator_memory | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |

## Interpretation

- `agent_output_schema_valid_rate` is structural schema validation only.
- Semantic execution health is tracked by `agent_task_success_rate`, `agent_failed_status_rate`, and `llm_setup_error_rate`.
- A run can have `agent_output_schema_valid_rate = 1.0` while still failing tasks if outputs are schema-valid but semantically failed (for example missing API key setup errors).
