# Trace Difference Analysis

- Generated at: 2026-05-08T12:25:58.775143+00:00
- Base directory: `experiments\stabilization_sprint_20260508`
- Episode rows: 100
- CSV: `experiments\stabilization_sprint_20260508\trace_differences.csv`

## Key Findings

- Episodes with retrieve_memory events: 66/100
- Episodes where scheduling decisions changed: 75/100
- Episodes where differences are retrieve_memory-only instrumentation: 16/100
- support_only_count (retrieve events): 394
- changed_agent_selection_count (retrieve events): 42
- changed_ordering_count (retrieve events): 0
- changed_recovery_count (retrieve events): 0

## Aggregate Metrics

| Metric | mas_no_memory | mas_orchestrator_memory | Delta (mem - no_mem) |
|---|---:|---:|---:|
| Agent call count | 521 | 525 | 4 |
| Retry count | 115 | 121 | 6 |
| Replan count | 0 | 0 | 0 |
| Total cost | 0.0 | 0.0 | 0.0 |
| Total latency sec | 106.184 | 110.117 | 3.933 |

## Episodes With Scheduling Changes

- episode_idx=0, task_family=evidence_based_writing, no_agents=writer|researcher|researcher|researcher, mem_agents=planner|researcher|writer|writer, diff=0:call_agent:writer != call_agent:planner; 2:call_agent:researcher != call_agent:writer; 3:call_agent:researcher != call_agent:writer
- episode_idx=2, task_family=evidence_based_writing, no_agents=planner|researcher|writer|critic, mem_agents=researcher|researcher|researcher|researcher|researcher|researcher, diff=0:call_agent:planner != call_agent:researcher; 1:call_agent:researcher != retry; 2:call_agent:writer != call_agent:researcher; 3:call_agent:critic != call_agent:researcher; 4:finalize != retry; 5:<none> != call_agent:researcher; 6:<none> != call_agent:researcher; 7:<none> != call_agent:researcher; ...
- episode_idx=3, task_family=dynamic_recovery, no_agents=writer|writer|recovery|recovery|recovery, mem_agents=planner|planner|researcher|writer|critic, diff=0:call_agent:writer != call_agent:planner; 1:call_agent:writer != retry; 2:call_agent:recovery != call_agent:planner; 3:call_agent:recovery != call_agent:researcher; 4:retry != call_agent:writer; 5:call_agent:recovery != call_agent:critic
- episode_idx=4, task_family=debugging, no_agents=planner|researcher|writer|critic|critic|critic, mem_agents=researcher|researcher|critic|critic|writer, diff=0:call_agent:planner != call_agent:researcher; 1:call_agent:researcher != retry; 2:call_agent:writer != call_agent:researcher; 4:retry != call_agent:critic; 5:call_agent:critic != call_agent:writer; 6:retry != finalize; 7:call_agent:critic != <none>; 8:finalize != <none>
- episode_idx=5, task_family=evidence_based_writing, no_agents=writer|researcher|researcher|researcher|researcher|researcher, mem_agents=researcher|researcher|researcher|researcher, diff=0:call_agent:writer != call_agent:researcher; 3:retry != call_agent:researcher; 4:call_agent:researcher != finalize; 5:call_agent:researcher != <none>; 6:retry != <none>; 7:call_agent:researcher != <none>; 8:finalize != <none>
- episode_idx=7, task_family=dynamic_recovery, no_agents=writer|writer|recovery|recovery|recovery|recovery, mem_agents=researcher|recovery|recovery|recovery|recovery, diff=0:call_agent:writer != call_agent:researcher; 1:call_agent:writer != call_agent:recovery; 3:call_agent:recovery != retry; 4:retry != call_agent:recovery; 6:retry != finalize; 7:call_agent:recovery != <none>; 8:finalize != <none>
- episode_idx=8, task_family=dynamic_recovery, no_agents=writer|writer|writer|recovery|recovery|recovery, mem_agents=researcher|researcher|recovery|recovery|recovery|recovery, diff=0:call_agent:writer != call_agent:researcher; 2:call_agent:writer != call_agent:researcher; 3:call_agent:writer != call_agent:recovery; 4:call_agent:recovery != retry; 5:retry != call_agent:recovery
- episode_idx=11, task_family=data_analysis, no_agents=planner|researcher|writer|writer|critic, mem_agents=planner|researcher|researcher|writer|critic, diff=2:call_agent:writer != retry; 3:retry != call_agent:researcher
- episode_idx=12, task_family=form_submission, no_agents=planner|researcher|writer|writer, mem_agents=critic|researcher|researcher|critic|writer, diff=0:call_agent:planner != call_agent:critic; 2:call_agent:writer != retry; 3:call_agent:writer != call_agent:researcher; 4:finalize != call_agent:critic; 5:<none> != call_agent:writer; 6:<none> != finalize
- episode_idx=13, task_family=multi_source_conflict, no_agents=planner|planner|planner|researcher|writer|writer|writer|writer, mem_agents=critic|researcher|critic|critic|writer, diff=0:call_agent:planner != call_agent:critic; 1:retry != call_agent:researcher; 2:call_agent:planner != call_agent:critic; 4:call_agent:planner != call_agent:critic; 5:call_agent:researcher != call_agent:writer; 6:call_agent:writer != finalize; 7:call_agent:writer != <none>; 8:retry != <none>; ...
- episode_idx=14, task_family=code_review, no_agents=planner|planner|planner|recovery|researcher|researcher|researcher|writer|critic, mem_agents=planner|researcher|writer|critic, diff=1:retry != call_agent:researcher; 2:call_agent:planner != call_agent:writer; 3:retry != call_agent:critic; 4:call_agent:planner != finalize; 5:call_recovery_agent:recovery != <none>; 6:call_agent:researcher != <none>; 7:retry != <none>; 8:call_agent:researcher != <none>; ...
- episode_idx=16, task_family=form_submission, no_agents=planner|researcher|researcher|writer|critic, mem_agents=critic|critic|researcher|researcher|critic|writer, diff=0:call_agent:planner != call_agent:critic; 1:call_agent:researcher != retry; 2:retry != call_agent:critic; 4:call_agent:writer != retry; 5:call_agent:critic != call_agent:researcher; 6:finalize != call_agent:critic; 7:<none> != call_agent:writer; 8:<none> != finalize
- episode_idx=17, task_family=evidence_based_writing, no_agents=writer|researcher|researcher|researcher|recovery|researcher|researcher, mem_agents=planner|planner|researcher|writer|writer|critic, diff=0:call_agent:writer != call_agent:planner; 1:call_agent:researcher != retry; 2:retry != call_agent:planner; 4:retry != call_agent:writer; 5:call_agent:researcher != retry; 6:call_recovery_agent:recovery != call_agent:writer; 7:call_agent:researcher != call_agent:critic; 8:call_agent:researcher != finalize; ...
- episode_idx=18, task_family=content_creation, no_agents=planner|researcher|writer|writer|writer, mem_agents=planner|researcher|writer|critic, diff=3:call_agent:writer != call_agent:critic; 4:retry != finalize; 5:call_agent:writer != <none>; 6:finalize != <none>
- episode_idx=19, task_family=debugging, no_agents=writer|writer|writer|writer|writer|critic|critic|writer, mem_agents=planner|researcher|writer|critic, diff=0:call_agent:writer != call_agent:planner; 1:retry != call_agent:researcher; 3:call_agent:writer != call_agent:critic; 4:retry != finalize; 5:call_agent:writer != <none>; 6:retry != <none>; 7:call_agent:writer != <none>; 8:call_agent:critic != <none>; ...
