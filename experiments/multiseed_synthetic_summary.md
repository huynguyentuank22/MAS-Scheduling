# Multi-Seed Synthetic Summary

- Seeds: 0, 1, 2, 3, 4
- Episodes per seed: 100
- Variants: mas_no_memory, mas_orchestrator_memory, mas_shuffled_memory, mas_random_memory

## Aggregate Metrics (mean +/- std)

| Variant | Success Rate | Mean Score | Order Viol. | Missing Req. | Mem Changed | Eligible | Blocked | Curator Accept | Curator Reject |
|---|---|---|---|---|---|---|---|---|---|
| mas_no_memory | 0.292 +/- 0.043 | 0.474 +/- 0.026 | 0.823 +/- 0.061 | 0.139 +/- 0.005 | 0.000 +/- 0.000 | 0.000 +/- 0.000 | 0.000 +/- 0.000 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| mas_orchestrator_memory | 0.420 +/- 0.063 | 0.581 +/- 0.045 | 0.567 +/- 0.067 | 0.115 +/- 0.010 | 71.600 +/- 19.113 | 432.200 +/- 53.148 | 0.000 +/- 0.000 | 0.452 +/- 0.069 | 0.548 +/- 0.069 |
| mas_shuffled_memory | 0.314 +/- 0.064 | 0.506 +/- 0.046 | 0.709 +/- 0.133 | 0.149 +/- 0.027 | 10.400 +/- 9.529 | 62.600 +/- 57.522 | 471.600 +/- 65.801 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |
| mas_random_memory | 0.314 +/- 0.064 | 0.506 +/- 0.046 | 0.709 +/- 0.133 | 0.149 +/- 0.027 | 10.400 +/- 9.529 | 62.600 +/- 57.522 | 471.600 +/- 65.801 | 0.000 +/- 0.000 | 0.000 +/- 0.000 |

## Seedwise Comparison Diagnostics

- Orchestrator vs no-memory (mean_score): wins/ties/losses = 5/0/0
- Orchestrator vs no-memory (success_rate): wins/ties/losses = 5/0/0
- Orchestrator vs shuffled (mean_score): wins/ties/losses = 5/0/0
- Orchestrator vs random (mean_score): wins/ties/losses = 5/0/0

## Answers

1. Is orchestrator memory consistently better than no-memory?
- Yes (based on seedwise mean_score and success_rate comparisons).

2. Is orchestrator memory consistently better than shuffled/random memory?
- Shuffled: Yes; Random: Yes.

3. Is the remaining shuffled advantage just single-seed noise?
- Yes (shuffled beats orchestrator in 0 seed(s)).

4. Is synthetic benchmark ready to freeze?
- Yes (use this with your domain judgment on robustness and external validity).

