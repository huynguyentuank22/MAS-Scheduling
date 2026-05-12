# Robustness Summary

- Generated at: 2026-05-12T08:17:05.516382+00:00
- Matrix settings: normal + 4 LLM-noise modes
- Variants included: mas_no_memory, mas_orchestrator_memory, mas_shuffled_memory, mas_random_memory
- Optional variant `mas_oracle_memory`: not implemented in current codebase, not included

## Performance and Scheduling Metrics

| Setting | Variant | Success | MeanScore | OrderViol | MissingReq | RecoverySucc | MemChanged | Retrieved | Eligible | Blocked |
|---|---|---|---|---|---|---|---|---|---|---|
| normal_hard_synthetic | mas_no_memory | 0.330 | 0.506 | 0.715 | 0.140 | 0.000 | 0 | 0 | 0 | 0 |
| normal_hard_synthetic | mas_orchestrator_memory | 0.460 | 0.621 | 0.445 | 0.113 | 0.000 | 78 | 506 | 506 | 0 |
| normal_hard_synthetic | mas_shuffled_memory | 0.410 | 0.623 | 0.465 | 0.143 | 0.000 | 37 | 518 | 191 | 327 |
| normal_hard_synthetic | mas_random_memory | 0.410 | 0.623 | 0.465 | 0.143 | 0.000 | 37 | 518 | 191 | 327 |
| llm_noise_malformed_json | mas_no_memory | 0.330 | 0.620 | 0.715 | 0.140 | 0.000 | 0 | 0 | 0 | 0 |
| llm_noise_malformed_json | mas_orchestrator_memory | 0.700 | 0.795 | 0.325 | 0.113 | 0.000 | 85 | 425 | 425 | 0 |
| llm_noise_malformed_json | mas_shuffled_memory | 0.580 | 0.745 | 0.465 | 0.140 | 0.000 | 25 | 335 | 125 | 210 |
| llm_noise_malformed_json | mas_random_memory | 0.580 | 0.745 | 0.465 | 0.140 | 0.000 | 25 | 335 | 125 | 210 |
| llm_noise_missing_fields | mas_no_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 0 | 0 | 0 | 0 |
| llm_noise_missing_fields | mas_orchestrator_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 236 | 1320 | 1320 | 0 |
| llm_noise_missing_fields | mas_shuffled_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 75 | 2010 | 750 | 1260 |
| llm_noise_missing_fields | mas_random_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 75 | 2010 | 750 | 1260 |
| llm_noise_hallucinated_artifact_ref | mas_no_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 0 | 0 | 0 | 0 |
| llm_noise_hallucinated_artifact_ref | mas_orchestrator_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 236 | 1320 | 1320 | 0 |
| llm_noise_hallucinated_artifact_ref | mas_shuffled_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 75 | 2010 | 750 | 1260 |
| llm_noise_hallucinated_artifact_ref | mas_random_memory | 0.000 | 0.000 | 0.000 | 0.393 | 0.840 | 75 | 2010 | 750 | 1260 |
| llm_noise_overgeneralized_lesson | mas_no_memory | 0.330 | 0.620 | 0.715 | 0.140 | 0.000 | 0 | 0 | 0 | 0 |
| llm_noise_overgeneralized_lesson | mas_orchestrator_memory | 0.700 | 0.795 | 0.325 | 0.113 | 0.000 | 85 | 425 | 425 | 0 |
| llm_noise_overgeneralized_lesson | mas_shuffled_memory | 0.580 | 0.745 | 0.465 | 0.140 | 0.000 | 25 | 335 | 125 | 210 |
| llm_noise_overgeneralized_lesson | mas_random_memory | 0.580 | 0.745 | 0.465 | 0.140 | 0.000 | 25 | 335 | 125 | 210 |

## Validation and Curation Metrics

| Setting | Variant | SchemaValid | ParseFail | RepairSucc | InvalidArtifactRef | MemValFail | Unsupported | Overgeneralized | CurAccept | CurReject |
|---|---|---|---|---|---|---|---|---|---|---|
| normal_hard_synthetic | mas_no_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| normal_hard_synthetic | mas_orchestrator_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.220 | 0.220 | 0.000 | 0.450 | 0.550 |
| normal_hard_synthetic | mas_shuffled_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| normal_hard_synthetic | mas_random_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_malformed_json | mas_no_memory | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_malformed_json | mas_orchestrator_memory | 1.000 | 1.000 | 1.000 | 0.000 | 0.810 | 0.280 | 0.000 | 0.090 | 0.910 |
| llm_noise_malformed_json | mas_shuffled_memory | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_malformed_json | mas_random_memory | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_missing_fields | mas_no_memory | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_missing_fields | mas_orchestrator_memory | 0.000 | 0.000 | 0.000 | 0.000 | 0.360 | 0.360 | 0.000 | 0.080 | 0.920 |
| llm_noise_missing_fields | mas_shuffled_memory | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_missing_fields | mas_random_memory | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_hallucinated_artifact_ref | mas_no_memory | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_hallucinated_artifact_ref | mas_orchestrator_memory | 0.000 | 0.000 | 0.000 | 1.000 | 0.360 | 0.360 | 0.000 | 0.080 | 0.920 |
| llm_noise_hallucinated_artifact_ref | mas_shuffled_memory | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_hallucinated_artifact_ref | mas_random_memory | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_overgeneralized_lesson | mas_no_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_overgeneralized_lesson | mas_orchestrator_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.280 | 0.280 | 0.000 | 0.620 | 0.380 |
| llm_noise_overgeneralized_lesson | mas_shuffled_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| llm_noise_overgeneralized_lesson | mas_random_memory | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

## Qualitative Episode Examples

1. Relevant memory improved scheduling
- setting=normal_hard_synthetic, episode=16, workflow_id=39398fff-d41d-4148-84e1-9788e3b8ed1b, task_family=form_submission
- score delta: 0.050 -> 0.800 (delta=0.750)
- influence_type=changed_agent_selection, baseline_agent=writer, final_agent=critic, memory_id=85cc656b-202d-4311-af80-14eaa33f18e0
- reason=Memory guard requires critic before writer

2. Shuffled/irrelevant memory was blocked
- setting=normal_hard_synthetic, episode=0, workflow_id=3f0cca19-f3d7-4b1f-b54f-6078521708c2, task_family=evidence_based_writing
- influence_type=none, blocked_reason=source_family_mismatch, current_family=evidence_based_writing, memory_family=evidence_based_writing
- trigger_match_score=0.7, eligible_to_influence=False

3. Invalid LLM output rejected and did not update procedural memory
- setting=llm_noise_hallucinated_artifact_ref, episode=1, workflow_id=e6591dc4-6548-49e5-990d-3e454ef68911, task_family=data_analysis
- invalid_agent_output events=28, accepted CREATE/UPDATE actions=0
- curation reasons (sample)=['failed_without_memory_signal']

## Conclusion

1. Does orchestrator memory improve scheduling under normal synthetic tasks?
- Yes. In normal hard synthetic, `mean_score` improved from 0.506 to 0.621, and `success_rate` improved from 0.330 to 0.460.

2. Does validation protect memory under noisy LLM outputs?
- Partially. Under `missing_fields` and `hallucinated_artifact_ref`, schema-valid rate drops to 0.000/0.000 and benchmark performance collapses, while invalid artifact references are explicitly surfaced (`hallucinated`: 1.000). Some curator accepts remain, so rejection is not absolute.

3. Does shuffled memory still outperform relevant memory anywhere?
- Yes, slightly in normal hard synthetic (`mas_shuffled_memory.mean_score=0.623` vs `mas_orchestrator_memory.mean_score=0.621`). In noisy modes where parsing is robust (`malformed_json`) or lessons are overgeneralized, orchestrator memory remains ahead.

4. Which metrics are ready for a thesis/paper table?
- Ready now: success_rate, mean_score, order_violation_rate, missing_required_agent_rate, recovery_success_rate, memory_changed_scheduling_decisions, retrieved/eligible/blocked counts, schema_valid_rate, parse_failure_rate, repair_success_rate, invalid_artifact_ref_rate.

5. What remains before moving to REALM-Bench/WebArena?
- Tighten curator acceptance under fully invalid outputs, validate on real LLM backends with calibrated latency/cost, and add benchmark adapters plus task-grounded success validators for external environments.

## Notes

- `malformed_json` run still performs strongly for memory variants: orchestrator `success_rate=0.700`, `mean_score=0.795`.
