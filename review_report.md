# OLM-MAS Implementation Review

## Checklist Summary

| # | Requirement | Status | Notes |
|---|------------|--------|-------|
| 1 | Control/data plane separated | **PASS** | MemoryStore = control, Blackboard = data. No cross-contamination. |
| 2 | All decisions logged as DecisionEvent | **PARTIAL** | Retry resets task state but the retry itself has no trace event. `wait` and `replan` actions are logged as DecisionEvent but produce no ExecutionTraceEvent. |
| 3 | ExecutionTrace append-only JSONL | **PASS** | `TraceLogger._append()` opens file in mode `"a"`, writes one JSON line. |
| 4 | ProceduralControlMemory has all required fields | **PASS** | trigger, recommended_schedule, avoid, recommended_recovery, confidence, supporting_episodes, negative_cases, last_updated, status — all present. |
| 5 | Scheduler uses memory in memory-enabled variant | **PARTIAL** | Memory is *retrieved* and `memory_refs` are attached, but `_select_agent` blindly returns the first agent in `recommended_schedule` regardless of task content. Memory never actually changes the agent selection for the better. |
| 6 | No-memory variant disables procedural retrieval | **PASS** | `Scheduler.__init__` receives `memory_store=None, use_memory=False` when disabled. Guard at line 73: `if self._use_memory and self._memory_store`. |
| 7 | Evaluator produces scheduling-specific metrics | **PASS** | `scheduling_scores` dict includes: agent_assignment_quality, dependency_violation_rate, unnecessary_agent_calls, replan_count, retry_count, recovery_success_rate, task_completion_rate. |
| 8 | Curator decides CREATE/UPDATE/IGNORE/DEPRECATE | **PASS** | All four paths exist and are tested. |
| 9 | Hard PolicyRules protected from modification | **PARTIAL** | Hard rules are *respected* at check time, but nothing prevents calling `PolicyEngine.add_rule()` with a contradicting allow rule at higher priority that would override a hard deny. |
| 10 | Synthetic benchmark runs end-to-end with metrics | **PASS** | Confirmed: CLI produces JSONL traces, metrics.json, comparison_report.json. |

---

## Issues by Severity

### HIGH — Logic bugs or missing functionality

#### H1. `_select_agent` ignores task context when memory is present
**File**: [scheduler.py:170-176](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/scheduler.py#L170-L176)

The memory-informed agent selection returns the *first* agent in `recommended_schedule` for *every* task, ignoring the task's actual description. A `research_report` memory with `["planner", "researcher", "writer", "critic"]` will always assign `planner` — even for the "Write the draft" subtask.

```python
# Current: blindly returns first recommendation
for rec in mem.recommended_schedule:
    if rec in [p.agent_type for p in self._registry.list_agents()]:
        return rec  # <-- always returns "planner"
```

**Fix**: Match the task description keywords against the recommended schedule list, falling through to keyword matching if no match.

#### H2. No `EpisodeReflection` is ever created
**File**: [orchestrator.py](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/orchestrator.py)

The `EpisodeReflection` schema is defined but never instantiated anywhere. The requirements say the system should produce "per-episode traces" and the reflection is part of the control plane.

**Fix**: Create an `EpisodeReflection` in the orchestrator after evaluation/curation and store it.

#### H3. PolicyEngine allows override of hard constraints via `add_rule`
**File**: [policy_engine.py:56-58](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/policy_engine.py#L56-L58)

`add_rule()` can insert an `allow` rule at priority 200 that shadows a hard `deny` rule at priority 100. The requirement states: "Policy hard constraints must not be silently modified by the orchestrator."

**Fix**: `add_rule()` should reject any rule that would override an existing hard constraint, or at minimum, hard deny rules should be checked first regardless of priority.

### MEDIUM — Gaps that weaken the experiment's validity

#### M1. Curator only creates memory when `not evaluation.memory_used`
**File**: [memory_curator.py:75](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/memory_curator.py#L75)

If an episode succeeds *with* memory, no new CREATE occurs. But different task families might need distinct memories. After the first successful episode for each family, only confidence updates happen — the system never learns new sub-patterns for the same family.

**Fix**: Also consider CREATE when the episode reveals a novel trigger (e.g., a previously-unseen task family even when some memory was retrieved for a different family).

#### M2. `recommended_recovery` is never populated in curator
**File**: [memory_curator.py:107](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/memory_curator.py#L107)

`ProceduralControlMemory.recommended_recovery` is always `[]`. The scheduler's retry/recovery logic doesn't consult it either.

**Fix**: Populate `recommended_recovery` from the evaluation's retry/recovery data; have the scheduler check it when deciding retry vs. recovery.

#### M3. Decision `cost` and `latency_sec` fields never populated
**File**: [orchestrator.py:125-133](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/orchestrator.py#L125-L133)

`DecisionEvent.cost` and `DecisionEvent.latency_sec` are always `None`. The actual agent latency is available from `result["latency_sec"]` but not written back to the decision.

**Fix**: Set `decision.latency_sec = result["latency_sec"]` and `decision.cost` from the agent profile's cost model after the agent call completes.

#### M4. Blackboard not cleared between episodes
**File**: [orchestrator.py](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/orchestrator.py)

The blackboard accumulates artifacts across episodes. With 50 episodes this is benign but conceptually wrong — later episodes could read artifacts from earlier ones through an accidental ID collision.

**Fix**: Clear the blackboard at the start of each episode, or scope artifact reads to the current `workflow_id`.

#### M5. `retrieve_memory` action type from architecture.md never emitted
**File**: [scheduler.py](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/scheduler.py)

The architecture doc lists `retrieve_memory` as a decision type, but retrieval happens silently inside the scheduler without producing a separate DecisionEvent. This makes it invisible in the trace.

**Fix**: Emit a `retrieve_memory` DecisionEvent when procedural memories are actually retrieved.

### LOW — Cleanups and robustness

#### L1. `active_memories` variable unused
**File**: [benchmark_runner.py:270](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/benchmark_runner.py#L270)

```python
active_memories = len(memory_store.list_procedural(status=None))
```
This variable is computed but never used in the output summary.

#### L2. Unused imports in `agent_runtime.py`
**File**: [agent_runtime.py:7,13](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/agent_runtime.py#L7-L13)

`time`, `Artifact`, `_now`, `_uuid` are imported but never used.

#### L3. `__main__.py` entry point doesn't route CLI args correctly
**File**: [\_\_main\_\_.py](file:///c:/Users/Admin/Documents/Tuan_Huy/antigravity_orchestrator_memory_pack/src/olm_mas/__main__.py)

Running `python -m olm_mas` (without `.cli`) falls through to `__main__.py` which calls `main()` without args. This actually works but the module path `olm_mas.cli` documented in the prompt requires `python -m olm_mas.cli`. The `__main__.py` should be at the package level for `python -m olm_mas`.

#### L4. No test for policy engine
No `test_policy_engine.py` exists. Hard constraint protection, tool filtering, and expiry logic are untested.

---

## Missing Requirements

| Requirement | Source | Status |
|-------------|--------|--------|
| EpisodeReflection populated | schemas.md | **Missing** — schema exists, never instantiated |
| `retrieve_memory` as logged DecisionEvent | architecture.md | **Missing** — retrieval is implicit |
| Agent profile `historical_performance` updated | schemas.md | **Missing** — field exists but never written |
| `decision_evaluations` list in SchedulingEvaluation | schemas.md | **Missing** — always `[]` |
| `spawn_agent` distinct from `call_agent` | architecture.md | **Not implemented** — only `call_agent` used |
| `ask_human` decision type | architecture.md | **Not implemented** |
| `write_blackboard` as explicit decision | architecture.md | **Not implemented** — writes happen implicitly |
| configs/system.yaml values used at runtime | system.yaml | **Partial** — confidence deltas match but other values (max_episode_steps, retrieval_top_k, etc.) are hardcoded |

---

## Concrete Code Changes

### Fix H1: Memory-aware agent selection

```diff
--- a/src/olm_mas/scheduler.py
+++ b/src/olm_mas/scheduler.py
@@ -167,11 +167,14 @@ class Scheduler:
     ) -> str:
         """Pick the best agent type for a task, considering memory hints."""
-        # Check memory recommendations first
+        # Check memory recommendations against task keywords
+        desc_lower = task.description.lower()
         for mem in memories:
             if mem.recommended_schedule:
-                for rec in mem.recommended_schedule:
-                    if rec in [p.agent_type for p in self._registry.list_agents()]:
-                        return rec
+                # Find which recommended agent matches this task's keywords
+                for keyword, agent_type in _KEYWORD_AGENT_MAP.items():
+                    if keyword in desc_lower and agent_type in mem.recommended_schedule:
+                        if self._registry.get(agent_type):
+                            return agent_type
 
         # Keyword matching fallback
-        desc_lower = task.description.lower()
         for keyword, agent_type in _KEYWORD_AGENT_MAP.items():
```

### Fix H3: Protect hard constraints in `add_rule`

```diff
--- a/src/olm_mas/policy_engine.py
+++ b/src/olm_mas/policy_engine.py
@@ -55,7 +55,17 @@ class PolicyEngine:
 
-    def add_rule(self, rule: PolicyRule) -> None:
+    def add_rule(self, rule: PolicyRule) -> bool:
+        """Add a rule. Returns False if it would override a hard constraint."""
+        if rule.action == "allow":
+            for existing in self._rules:
+                if not existing.is_hard_constraint:
+                    continue
+                if existing.action != "deny":
+                    continue
+                if self._scope_matches(existing.object_scope, rule.object_scope):
+                    return False  # Would override hard deny
         self._rules.append(rule)
         self._rules.sort(key=lambda r: r.priority, reverse=True)
+        return True
```

### Fix H2: Create EpisodeReflection

```diff
--- a/src/olm_mas/orchestrator.py
+++ b/src/olm_mas/orchestrator.py
@@ -265,6 +265,18 @@ class Orchestrator:
         self._store.put_evaluation(evaluation)
 
+        # 5b. Create episode reflection
+        reflection = EpisodeReflection(
+            workflow_id=workflow.workflow_id,
+            outcome="success" if task_success else "failure",
+            root_cause_tags=evaluation.failure_factors,
+            reflection=f"Episode {'succeeded' if task_success else 'failed'} "
+                        f"with {len(decisions)} decisions",
+            reward_or_score=benchmark_score,
+            learned_memory_refs=[mid for _, mid in curation_actions if mid],
+        )
+
         # 6. Curate memory
```

### Fix M3: Populate decision cost/latency

```diff
--- a/src/olm_mas/orchestrator.py
+++ b/src/olm_mas/orchestrator.py
@@ -238,6 +238,8 @@ class Orchestrator:
                 decision.output_refs = [artifact.artifact_id]
                 target_task.state = TaskState.DONE
+            decision.latency_sec = result["latency_sec"]
+            decision.cost = profile.cost_model.get("relative_cost_value", 0.0)
             else:
                 target_task.state = TaskState.FAILED
```

---

## Tests to Add

| Test | File | What it verifies |
|------|------|-----------------|
| `test_policy_hard_constraint_protection` | `tests/test_policy_engine.py` | `add_rule()` rejects allow rules that override hard deny |
| `test_policy_tool_filtering` | `tests/test_policy_engine.py` | `filter_tools()` removes denied tools |
| `test_policy_expiry` | `tests/test_policy_engine.py` | Expired rules are skipped |
| `test_memory_informed_agent_selection` | `tests/test_scheduler.py` | With memory, scheduler picks task-appropriate agent (not blindly first) |
| `test_episode_reflection_created` | `tests/test_synthetic_run.py` | Orchestrator produces an EpisodeReflection |
| `test_decision_latency_populated` | `tests/test_synthetic_run.py` | DecisionEvent.latency_sec is set after agent call |
| `test_retrieve_memory_decision_logged` | `tests/test_scheduler.py` | When memory retrieval happens, a `retrieve_memory` DecisionEvent is emitted |
| `test_blackboard_isolation_across_episodes` | `tests/test_synthetic_run.py` | Artifacts from episode N are not visible in episode N+1 |
| `test_curator_creates_for_novel_family` | `tests/test_memory_update.py` | Curator creates new memory even when some memory was used, if trigger is novel |
