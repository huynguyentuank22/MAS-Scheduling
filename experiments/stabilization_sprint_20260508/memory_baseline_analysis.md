# Memory Baseline Analysis

- Generated at: 2026-05-08T12:26:08.873764+00:00
- Run directory: `experiments\stabilization_sprint_20260508`

## 1) Per-Variant Per-Family Metrics

| Variant | Family | Episodes | Success Rate | Mean Score | Order Viol. Rate | Missing Req. Rate | Changed Decisions |
|---|---|---|---|---|---|---|---|
| mas_no_memory | code_review | 8 | 1.000 | 0.943 | 0.000 | 0.000 | 0 |
| mas_no_memory | content_creation | 7 | 1.000 | 0.949 | 0.000 | 0.000 | 0 |
| mas_no_memory | data_analysis | 6 | 1.000 | 0.967 | 0.000 | 0.000 | 0 |
| mas_no_memory | debugging | 12 | 0.000 | 0.392 | 0.500 | 0.333 | 0 |
| mas_no_memory | dynamic_recovery | 16 | 0.000 | 0.319 | 0.000 | 0.333 | 0 |
| mas_no_memory | evidence_based_writing | 14 | 0.000 | 0.214 | 2.000 | 0.333 | 0 |
| mas_no_memory | form_submission | 10 | 0.000 | 0.200 | 1.500 | 0.000 | 0 |
| mas_no_memory | multi_source_conflict | 15 | 0.000 | 0.253 | 1.500 | 0.000 | 0 |
| mas_no_memory | research_report | 8 | 1.000 | 0.930 | 0.000 | 0.000 | 0 |
| mas_no_memory | troubleshooting | 4 | 1.000 | 0.980 | 0.000 | 0.000 | 0 |
| mas_orchestrator_memory | code_review | 8 | 1.000 | 0.938 | 0.000 | 0.000 | 0 |
| mas_orchestrator_memory | content_creation | 7 | 1.000 | 0.983 | 0.000 | 0.000 | 0 |
| mas_orchestrator_memory | data_analysis | 6 | 1.000 | 0.913 | 0.000 | 0.000 | 0 |
| mas_orchestrator_memory | debugging | 12 | 0.667 | 0.758 | 0.000 | 0.000 | 33 |
| mas_orchestrator_memory | dynamic_recovery | 16 | 0.000 | 0.331 | 0.000 | 0.333 | 11 |
| mas_orchestrator_memory | evidence_based_writing | 14 | 0.000 | 0.293 | 1.429 | 0.428 | 5 |
| mas_orchestrator_memory | form_submission | 10 | 0.000 | 0.360 | 1.100 | 0.000 | 7 |
| mas_orchestrator_memory | multi_source_conflict | 15 | 0.200 | 0.437 | 0.967 | 0.000 | 10 |
| mas_orchestrator_memory | research_report | 8 | 1.000 | 0.945 | 0.000 | 0.000 | 0 |
| mas_orchestrator_memory | troubleshooting | 4 | 1.000 | 0.930 | 0.000 | 0.000 | 0 |
| mas_shuffled_memory | code_review | 8 | 1.000 | 0.917 | 0.000 | 0.000 | 0 |
| mas_shuffled_memory | content_creation | 7 | 1.000 | 0.971 | 0.000 | 0.000 | 0 |
| mas_shuffled_memory | data_analysis | 6 | 1.000 | 0.947 | 0.000 | 0.000 | 0 |
| mas_shuffled_memory | debugging | 12 | 0.000 | 0.442 | 0.500 | 0.333 | 0 |
| mas_shuffled_memory | dynamic_recovery | 16 | 0.000 | 0.431 | 0.000 | 0.333 | 0 |
| mas_shuffled_memory | evidence_based_writing | 14 | 0.000 | 0.257 | 2.000 | 0.333 | 0 |
| mas_shuffled_memory | form_submission | 10 | 0.300 | 0.675 | 0.500 | 0.000 | 11 |
| mas_shuffled_memory | multi_source_conflict | 15 | 0.267 | 0.687 | 0.500 | 0.000 | 18 |
| mas_shuffled_memory | research_report | 8 | 1.000 | 0.943 | 0.000 | 0.000 | 0 |
| mas_shuffled_memory | troubleshooting | 4 | 1.000 | 0.905 | 0.000 | 0.000 | 0 |

## 2) Memory Trigger vs Task Family Confusion

### mas_orchestrator_memory (trigger.task_family)
| Task Family | Trigger Family | Count |
|---|---|---|
| code_review | code_review | 108 |
| code_review | data_analysis | 10 |
| code_review | troubleshooting | 14 |
| content_creation | content_creation | 104 |
| content_creation | research_report | 14 |
| data_analysis | data_analysis | 90 |
| data_analysis | research_report | 28 |
| debugging | code_review | 18 |
| debugging | content_creation | 24 |
| debugging | data_analysis | 28 |
| debugging | debugging | 212 |
| debugging | research_report | 20 |
| debugging | troubleshooting | 14 |
| dynamic_recovery | dynamic_recovery | 60 |
| dynamic_recovery | research_report | 68 |
| dynamic_recovery | troubleshooting | 14 |
| evidence_based_writing | content_creation | 18 |
| evidence_based_writing | data_analysis | 24 |
| evidence_based_writing | evidence_based_writing | 52 |
| evidence_based_writing | research_report | 14 |
| form_submission | code_review | 14 |
| form_submission | content_creation | 14 |
| form_submission | data_analysis | 32 |
| form_submission | form_submission | 68 |
| form_submission | research_report | 20 |
| form_submission | troubleshooting | 14 |
| multi_source_conflict | code_review | 18 |
| multi_source_conflict | content_creation | 24 |
| multi_source_conflict | data_analysis | 28 |
| multi_source_conflict | multi_source_conflict | 116 |
| multi_source_conflict | research_report | 26 |
| multi_source_conflict | troubleshooting | 14 |
| research_report | code_review | 32 |
| research_report | content_creation | 14 |
| research_report | research_report | 90 |
| research_report | troubleshooting | 14 |
| troubleshooting | code_review | 14 |
| troubleshooting | troubleshooting | 50 |

### mas_shuffled_memory (trigger.task_family)
| Task Family | Trigger Family | Count |
|---|---|---|
| debugging | debugging | 194 |
| dynamic_recovery | dynamic_recovery | 244 |
| evidence_based_writing | evidence_based_writing | 182 |
| form_submission | form_submission | 154 |
| multi_source_conflict | multi_source_conflict | 215 |

### Source-Family Lineage (if present)
| Variant | Task Family | Source Family | Count |
|---|---|---|---|
| mas_orchestrator_memory | code_review | code_review | 108 |
| mas_orchestrator_memory | code_review | data_analysis | 10 |
| mas_orchestrator_memory | code_review | troubleshooting | 14 |
| mas_orchestrator_memory | content_creation | content_creation | 104 |
| mas_orchestrator_memory | content_creation | research_report | 14 |
| mas_orchestrator_memory | data_analysis | data_analysis | 90 |
| mas_orchestrator_memory | data_analysis | research_report | 28 |
| mas_orchestrator_memory | debugging | code_review | 18 |
| mas_orchestrator_memory | debugging | content_creation | 24 |
| mas_orchestrator_memory | debugging | data_analysis | 28 |
| mas_orchestrator_memory | debugging | debugging | 212 |
| mas_orchestrator_memory | debugging | research_report | 20 |
| mas_orchestrator_memory | debugging | troubleshooting | 14 |
| mas_orchestrator_memory | dynamic_recovery | dynamic_recovery | 60 |
| mas_orchestrator_memory | dynamic_recovery | research_report | 68 |
| mas_orchestrator_memory | dynamic_recovery | troubleshooting | 14 |
| mas_orchestrator_memory | evidence_based_writing | content_creation | 18 |
| mas_orchestrator_memory | evidence_based_writing | data_analysis | 24 |
| mas_orchestrator_memory | evidence_based_writing | evidence_based_writing | 52 |
| mas_orchestrator_memory | evidence_based_writing | research_report | 14 |
| mas_orchestrator_memory | form_submission | code_review | 14 |
| mas_orchestrator_memory | form_submission | content_creation | 14 |
| mas_orchestrator_memory | form_submission | data_analysis | 32 |
| mas_orchestrator_memory | form_submission | form_submission | 68 |
| mas_orchestrator_memory | form_submission | research_report | 20 |
| mas_orchestrator_memory | form_submission | troubleshooting | 14 |
| mas_orchestrator_memory | multi_source_conflict | code_review | 18 |
| mas_orchestrator_memory | multi_source_conflict | content_creation | 24 |
| mas_orchestrator_memory | multi_source_conflict | data_analysis | 28 |
| mas_orchestrator_memory | multi_source_conflict | multi_source_conflict | 116 |
| mas_orchestrator_memory | multi_source_conflict | research_report | 26 |
| mas_orchestrator_memory | multi_source_conflict | troubleshooting | 14 |
| mas_orchestrator_memory | research_report | code_review | 32 |
| mas_orchestrator_memory | research_report | content_creation | 14 |
| mas_orchestrator_memory | research_report | research_report | 90 |
| mas_orchestrator_memory | research_report | troubleshooting | 14 |
| mas_orchestrator_memory | troubleshooting | code_review | 14 |
| mas_orchestrator_memory | troubleshooting | troubleshooting | 50 |
| mas_shuffled_memory | debugging | evidence_based_writing | 194 |
| mas_shuffled_memory | dynamic_recovery | debugging | 244 |
| mas_shuffled_memory | evidence_based_writing | dynamic_recovery | 182 |
| mas_shuffled_memory | form_submission | form_submission | 154 |
| mas_shuffled_memory | multi_source_conflict | multi_source_conflict | 215 |

## 3) Top Retrieved Memory IDs / Triggers Per Family

| Variant | Task Family | Memory ID | Trigger Family | Source Family | Count |
|---|---|---|---|---|---|
| mas_orchestrator_memory | code_review | 725a3f81-1a5b-47fb-b00f-4b958aace7b8 | code_review |  | 49 |
| mas_orchestrator_memory | code_review | 4b7af98d-2e35-4c01-bc5b-6c16ca418ebc | code_review |  | 49 |
| mas_orchestrator_memory | code_review | f9916f59-e857-4e17-90ad-c60e5bffb8fd | troubleshooting |  | 7 |
| mas_orchestrator_memory | content_creation | 1cab6efa-dfa3-4688-a775-5819a128ec8a | content_creation |  | 36 |
| mas_orchestrator_memory | content_creation | 185cc9ef-55d0-4d0c-926e-5a3ed7d2f593 | content_creation |  | 36 |
| mas_orchestrator_memory | content_creation | e213f316-066e-40e6-952e-502eae0a40a1 | content_creation |  | 16 |
| mas_orchestrator_memory | data_analysis | ab3b13ed-4068-4035-9fac-a75a65569305 | data_analysis |  | 45 |
| mas_orchestrator_memory | data_analysis | 8f391f64-6e38-46ef-8b3e-b9a83b2fb01b | data_analysis |  | 45 |
| mas_orchestrator_memory | data_analysis | da8edf39-bb77-4a04-ac0a-bc951a352d6d | research_report |  | 14 |
| mas_orchestrator_memory | debugging | ab5b9c04-77b3-4686-9561-d4b529ee9433 | debugging | debugging | 106 |
| mas_orchestrator_memory | debugging | 158dd7a4-a12e-41b3-a62f-8d5ecb6df0b3 | debugging | debugging | 106 |
| mas_orchestrator_memory | debugging | 873fa517-edd5-42da-bbfe-dd12abff7404 | data_analysis |  | 14 |
| mas_orchestrator_memory | dynamic_recovery | da8edf39-bb77-4a04-ac0a-bc951a352d6d | research_report |  | 34 |
| mas_orchestrator_memory | dynamic_recovery | 93d3ad73-8ff3-43af-a2f7-58ce55d59572 | research_report |  | 34 |
| mas_orchestrator_memory | dynamic_recovery | f2174637-20e1-4774-aec3-902e73e652a9 | dynamic_recovery | dynamic_recovery | 30 |
| mas_orchestrator_memory | evidence_based_writing | b36be4dc-4fc4-46fa-ab70-393952186cfb | evidence_based_writing | evidence_based_writing | 26 |
| mas_orchestrator_memory | evidence_based_writing | 2bd968ec-a926-40a0-851e-5d71100c79aa | evidence_based_writing | evidence_based_writing | 26 |
| mas_orchestrator_memory | evidence_based_writing | 873fa517-edd5-42da-bbfe-dd12abff7404 | data_analysis |  | 12 |
| mas_orchestrator_memory | form_submission | 9e18ec9c-354a-436c-aca1-8d9f5b5c252b | form_submission | form_submission | 34 |
| mas_orchestrator_memory | form_submission | 66f04189-32a3-4e25-bb4b-53c932f60c81 | form_submission | form_submission | 34 |
| mas_orchestrator_memory | form_submission | 873fa517-edd5-42da-bbfe-dd12abff7404 | data_analysis |  | 16 |
| mas_orchestrator_memory | multi_source_conflict | cb45b842-b584-4397-9231-149cda45883f | multi_source_conflict | multi_source_conflict | 58 |
| mas_orchestrator_memory | multi_source_conflict | bbaef215-7103-472d-be46-7e02ba72f0ea | multi_source_conflict | multi_source_conflict | 58 |
| mas_orchestrator_memory | multi_source_conflict | 873fa517-edd5-42da-bbfe-dd12abff7404 | data_analysis |  | 14 |
| mas_orchestrator_memory | research_report | 903812d2-fcf8-453e-b829-37e6ae9037ed | research_report |  | 45 |
| mas_orchestrator_memory | research_report | 1cf3b2c8-486b-49a1-9498-cbb9f7f27b33 | research_report |  | 45 |
| mas_orchestrator_memory | research_report | d103440a-f1a4-4c8a-977c-f45d7fee44ef | code_review |  | 16 |
| mas_orchestrator_memory | troubleshooting | ba7926ad-6468-4c37-bf26-145a88bb08f3 | troubleshooting |  | 25 |
| mas_orchestrator_memory | troubleshooting | 966b7962-dc64-48f9-bab5-effd232e2bc6 | troubleshooting |  | 25 |
| mas_orchestrator_memory | troubleshooting | d103440a-f1a4-4c8a-977c-f45d7fee44ef | code_review |  | 7 |
| mas_shuffled_memory | debugging | 22fca269-51ca-4f80-88ef-57b4d0d82051 | debugging | evidence_based_writing | 98 |
| mas_shuffled_memory | debugging | 3cb5febb-2c4f-4c35-a74a-1e3bdcbb7f0b | debugging | evidence_based_writing | 96 |
| mas_shuffled_memory | dynamic_recovery | 820afdec-004d-4dd0-a759-670255772865 | dynamic_recovery | debugging | 127 |
| mas_shuffled_memory | dynamic_recovery | 5c40b80b-aa4d-41f5-bdb8-cdf0c5c71904 | dynamic_recovery | debugging | 117 |
| mas_shuffled_memory | evidence_based_writing | 2676a723-c0d9-41fd-9741-5442e6c8d6bb | evidence_based_writing | dynamic_recovery | 96 |
| mas_shuffled_memory | evidence_based_writing | f2485b8b-3433-43e1-877c-3c8db9710763 | evidence_based_writing | dynamic_recovery | 86 |
| mas_shuffled_memory | form_submission | 8be29d2b-3125-42a6-8fb1-dc0f79db4436 | form_submission | form_submission | 79 |
| mas_shuffled_memory | form_submission | fb58f616-7d81-4d89-8187-9ea1cada5d13 | form_submission | form_submission | 75 |
| mas_shuffled_memory | multi_source_conflict | eb8da17d-cd91-4413-8c06-7f127d72cbd9 | multi_source_conflict | multi_source_conflict | 109 |
| mas_shuffled_memory | multi_source_conflict | e71fe44e-da3d-456e-8c06-6fd3585d9e27 | multi_source_conflict | multi_source_conflict | 106 |

## 4) Influence Type Counts Per Family

| Variant | Task Family | Influence Type | Count |
|---|---|---|---|
| mas_orchestrator_memory | code_review | none | 17 |
| mas_orchestrator_memory | code_review | support_only | 115 |
| mas_orchestrator_memory | content_creation | none | 23 |
| mas_orchestrator_memory | content_creation | support_only | 95 |
| mas_orchestrator_memory | data_analysis | none | 14 |
| mas_orchestrator_memory | data_analysis | support_only | 104 |
| mas_orchestrator_memory | debugging | changed_agent_selection | 66 |
| mas_orchestrator_memory | debugging | none | 52 |
| mas_orchestrator_memory | debugging | support_only | 198 |
| mas_orchestrator_memory | dynamic_recovery | changed_agent_selection | 24 |
| mas_orchestrator_memory | dynamic_recovery | none | 41 |
| mas_orchestrator_memory | dynamic_recovery | support_only | 77 |
| mas_orchestrator_memory | evidence_based_writing | changed_agent_selection | 10 |
| mas_orchestrator_memory | evidence_based_writing | none | 28 |
| mas_orchestrator_memory | evidence_based_writing | support_only | 70 |
| mas_orchestrator_memory | form_submission | changed_agent_selection | 14 |
| mas_orchestrator_memory | form_submission | none | 47 |
| mas_orchestrator_memory | form_submission | support_only | 101 |
| mas_orchestrator_memory | multi_source_conflict | changed_agent_selection | 20 |
| mas_orchestrator_memory | multi_source_conflict | none | 55 |
| mas_orchestrator_memory | multi_source_conflict | support_only | 151 |
| mas_orchestrator_memory | research_report | none | 30 |
| mas_orchestrator_memory | research_report | support_only | 120 |
| mas_orchestrator_memory | troubleshooting | none | 7 |
| mas_orchestrator_memory | troubleshooting | support_only | 57 |
| mas_shuffled_memory | debugging | changed_agent_selection | 17 |
| mas_shuffled_memory | debugging | none | 98 |
| mas_shuffled_memory | debugging | support_only | 79 |
| mas_shuffled_memory | dynamic_recovery | changed_agent_selection | 45 |
| mas_shuffled_memory | dynamic_recovery | none | 117 |
| mas_shuffled_memory | dynamic_recovery | support_only | 82 |
| mas_shuffled_memory | evidence_based_writing | changed_agent_selection | 18 |
| mas_shuffled_memory | evidence_based_writing | none | 96 |
| mas_shuffled_memory | evidence_based_writing | support_only | 68 |
| mas_shuffled_memory | form_submission | changed_agent_selection | 26 |
| mas_shuffled_memory | form_submission | support_only | 128 |
| mas_shuffled_memory | multi_source_conflict | changed_agent_selection | 37 |
| mas_shuffled_memory | multi_source_conflict | support_only | 178 |

## 4b) Memory Eligibility Gate Diagnostics

| Variant | Retrieved | Eligible | Blocked | Blocked (Family Mismatch) | Applied Changed | Support Only |
|---|---|---|---|---|---|---|
| mas_no_memory | 0 | 0 | 0 | 0 | 0 | 0 |
| mas_orchestrator_memory | 1536 | 454 | 0 | 0 | 134 | 1088 |
| mas_shuffled_memory | 989 | 184 | 311 | 311 | 143 | 535 |

### Trigger Match Score Distribution by Variant

| Variant | Mean | P25 | P50 | P75 | Min | Max |
|---|---|---|---|---|---|---|
| mas_no_memory | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| mas_orchestrator_memory | 0.207 | 0.000 | 0.000 | 0.700 | 0.000 | 0.700 |
| mas_shuffled_memory | 0.350 | 0.000 | 0.700 | 0.700 | 0.000 | 0.700 |

## 5) Examples Where Shuffled Memory Improved Score

| Episode | Family | Shuffled | Orchestrator | Delta | Top Memory | Trigger | Source |
|---|---|---|---|---|---|---|---|
| 97 | multi_source_conflict | 0.800 | 0.100 | 0.700 | e71fe44e-da3d-456e-8c06-6fd3585d9e27 | multi_source_conflict | multi_source_conflict |
| 89 | multi_source_conflict | 0.700 | 0.050 | 0.650 | e71fe44e-da3d-456e-8c06-6fd3585d9e27 | multi_source_conflict | multi_source_conflict |
| 30 | form_submission | 0.800 | 0.200 | 0.600 | fb58f616-7d81-4d89-8187-9ea1cada5d13 | form_submission | form_submission |
| 36 | form_submission | 0.700 | 0.100 | 0.600 | fb58f616-7d81-4d89-8187-9ea1cada5d13 | form_submission | form_submission |
| 69 | multi_source_conflict | 0.700 | 0.100 | 0.600 | eb8da17d-cd91-4413-8c06-7f127d72cbd9 | multi_source_conflict | multi_source_conflict |
| 74 | form_submission | 0.700 | 0.100 | 0.600 | 8be29d2b-3125-42a6-8fb1-dc0f79db4436 | form_submission | form_submission |
| 82 | dynamic_recovery | 0.600 | 0.050 | 0.550 | 820afdec-004d-4dd0-a759-670255772865 | dynamic_recovery | debugging |
| 57 | dynamic_recovery | 0.500 | 0.000 | 0.500 | 5c40b80b-aa4d-41f5-bdb8-cdf0c5c71904 | dynamic_recovery | debugging |

## 6) Examples Where Shuffled Memory Caused Negative Transfer

| Episode | Family | Shuffled | No Memory | Delta | Top Memory | Trigger | Source |
|---|---|---|---|---|---|---|---|
| 35 | dynamic_recovery | 0.000 | 0.600 | -0.600 | 820afdec-004d-4dd0-a759-670255772865 | dynamic_recovery | debugging |
| 15 | debugging | 0.300 | 0.600 | -0.300 | 3cb5febb-2c4f-4c35-a74a-1e3bdcbb7f0b | debugging | evidence_based_writing |
| 66 | evidence_based_writing | 0.150 | 0.350 | -0.200 | 2676a723-c0d9-41fd-9741-5442e6c8d6bb | evidence_based_writing | dynamic_recovery |
| 27 | debugging | 0.400 | 0.600 | -0.200 | 22fca269-51ca-4f80-88ef-57b4d0d82051 | debugging | evidence_based_writing |
| 93 | evidence_based_writing | 0.150 | 0.250 | -0.100 | 2676a723-c0d9-41fd-9741-5442e6c8d6bb | evidence_based_writing | dynamic_recovery |
| 34 | debugging | 0.400 | 0.500 | -0.100 | 3cb5febb-2c4f-4c35-a74a-1e3bdcbb7f0b | debugging | evidence_based_writing |
| 48 | dynamic_recovery | 0.500 | 0.600 | -0.100 | 5c40b80b-aa4d-41f5-bdb8-cdf0c5c71904 | dynamic_recovery | debugging |
| 81 | dynamic_recovery | 0.500 | 0.600 | -0.100 | 5c40b80b-aa4d-41f5-bdb8-cdf0c5c71904 | dynamic_recovery | debugging |

## 7) Is Memory Matching Too Permissive?

| Variant | Retrieved Refs | Trigger Mismatch | Trigger Mismatch Rate | Source Mismatch | Source Mismatch Rate | Verdict | Reason |
|---|---|---|---|---|---|---|---|
| mas_orchestrator_memory | 1536 | 586/1536 | 0.382 | 0/508 | 0.000 | too_permissive_by_trigger | High trigger-task mismatch in retrieved refs |
| mas_shuffled_memory | 989 | 0/989 | 0.000 | 620/989 | 0.627 | too_permissive_by_content | Retrieved memories often originate from different source_family while still matching by task_family trigger |

## Why Shuffled Can Outscore Orchestrator Here

- `mas_shuffled_memory.mean_score=0.638` vs `mas_orchestrator_memory.mean_score=0.598`.
- Current retrieval matching keys primarily on `trigger.task_family`; shuffled seeds can still match the same family even when `source_family` differs.
- Several shuffled memories carry generic schedules/avoid rules that accidentally help hard-family penalties (especially ordering penalties), producing positive transfer in some episodes.
- Orchestrator-memory run mixes seeded + curated memories, and curation may reinforce suboptimal but high-confidence patterns for some families, reducing relative score on this run.

