# Synthetic Results Summary

## Scope
- This summary covers the hard synthetic benchmark families, ablation variants, multi-seed stability, and LLM-noise robustness runs completed before external benchmark integration.
- Source outputs include:
- `experiments/multiseed_synthetic_summary.csv`
- `experiments/multiseed_synthetic_summary.md`
- `experiments/robustness_summary.csv`
- `experiments/robustness_summary.md`

## Hard Synthetic Families
- `evidence_based_writing`
- `multi_source_conflict`
- `form_submission`
- `debugging`
- `dynamic_recovery`

## Ablation Variants
- `mas_no_memory`
- `mas_orchestrator_memory`
- `mas_shuffled_memory`
- `mas_random_memory`

## Multi-Seed Results (Seeds 0..4, 100 Episodes/Seed)
- `mas_no_memory`: success_rate `0.292 +/- 0.043`, mean_score `0.474 +/- 0.026`
- `mas_orchestrator_memory`: success_rate `0.420 +/- 0.063`, mean_score `0.581 +/- 0.045`
- `mas_shuffled_memory`: success_rate `0.314 +/- 0.064`, mean_score `0.506 +/- 0.046`
- `mas_random_memory`: success_rate `0.314 +/- 0.064`, mean_score `0.506 +/- 0.046`
- Seedwise comparison:
- Orchestrator vs no-memory mean_score wins/ties/losses: `5/0/0`
- Orchestrator vs shuffled mean_score wins/ties/losses: `5/0/0`
- Orchestrator vs random mean_score wins/ties/losses: `5/0/0`

## LLM-Noise Robustness Snapshot
- `malformed_json`:
- `mas_orchestrator_memory` success_rate `0.700`, mean_score `0.795`
- `mas_no_memory` success_rate `0.330`, mean_score `0.620`
- `missing_fields`:
- All variants collapse to success_rate `0.000`, mean_score `0.000`
- Schema-valid rate drops to `0.000`
- `hallucinated_artifact_ref`:
- All variants collapse to success_rate `0.000`, mean_score `0.000`
- Invalid artifact ref rate rises to `1.000`
- `overgeneralized_lesson`:
- `mas_orchestrator_memory` success_rate `0.700`, mean_score `0.795`

## Supported Claims
- Orchestrator-local memory improves scheduling quality over no-memory on hard synthetic tasks in multi-seed evaluation.
- Trigger-eligibility gating reduces harmful shuffled/random influence through higher blocked counts and lower eligible counts.
- Output-validation instrumentation is observable and effective at surfacing noisy output failure modes (`schema_valid_rate`, `invalid_artifact_ref_rate`, `parse_failure_rate`).
- Curator guardrails now block memory updates when invalid agent outputs are present.

## Limitations
- Synthetic tasks are still controlled abstractions and do not represent real web/file tool complexity.
- `missing_fields` and `hallucinated_artifact_ref` noise modes currently cause full benchmark collapse, indicating runtime robustness limits under severe corruption.
- Score improvements do not yet establish transfer to external benchmarks.
- Current GAIA-lite integration is for adapter/trace reliability and observability, not score optimization.
