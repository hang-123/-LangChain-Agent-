# Phase 6: Phase 1 Legacy Cleanup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Phase 1 graph and 8 purely-dead agent files, making Phase 2 the sole runtime graph and simplifying the codebase.

**Architecture:** After removal, `api/core/graph.py` only contains `build_phase2_graph()` (renamed to `build_graph()`). `api/main.py` uses a single graph without phase switching. The 8 agent files deleted are: `intent_router.py`, `insight_agent.py`, `job_intelligence_agent.py`, `matching_agent.py`, `quality_gate.py`, `query_agent.py`, `review_agent.py`, `offer_evaluator.py`. Four agent files with Phase 2 consumers (`search_agent.py`, `resume_tailor_agent.py`, `archetype_detector.py`, `legitimacy_scorer.py`) are kept.

**Tech Stack:** Python, git rm

---

## File Structure

### Delete
- `api/agents/intent_router.py`
- `api/agents/insight_agent.py`
- `api/agents/job_intelligence_agent.py`
- `api/agents/matching_agent.py`
- `api/agents/quality_gate.py`
- `api/agents/query_agent.py`
- `api/agents/review_agent.py`
- `api/agents/offer_evaluator.py`

### Modify
- `api/core/graph.py` — Remove `build_career_research_graph()`, Phase 1 imports, `route_after_review()`, `_parse_review_feedback`, `GRAPH_NODE_ORDER`; rename `build_phase2_graph` to `build_graph`
- `api/main.py` — Remove `_graph` global, remove `phase` field from request models, simplify `_get_graph()`
- `tests/test_research_api.py` — Remove `phase` field from test payloads if any

---

### Task 1: Remove Phase 1 Graph from graph.py

**Files:**
- Modify: `api/core/graph.py`

- [ ] **Step 1: Read current graph.py to understand the Phase 1 section**

Read `api/core/graph.py` fully to identify all Phase-1-only code.

- [ ] **Step 2: Remove Phase 1 imports (lines 10-25)**

Remove these imports from the top of the file:
```python
from api.agents.insight_agent import insight_agent_node
from api.agents.intent_router import intent_router_node
from api.agents.job_intelligence_agent import job_intelligence_agent_node
from api.agents.matching_agent import matching_agent_node
from api.agents.quality_gate import quality_gate_node
from api.agents.query_agent import query_agent_node
from api.agents.review_agent import review_agent_node
from api.agents.offer_evaluator import offer_evaluator_node
```
Also remove the import of `search_agent_node` (line 23) since it's only used by Phase 1 graph:
```python
from api.agents.search_agent import search_agent_node
```
Keep: `from api.agents.report_agent import report_agent_node`, `from api.agents.memory_retrieval import memory_retrieval_node`, `from api.agents.archetype_detector import archetype_detector_node`, `from api.agents.legitimacy_scorer import legitimacy_scorer_node` (though the last two are only used in Phase 1... check if they're still needed).

Actually, `archetype_detector_node` and `legitimacy_scorer_node` are Phase 1 nodes but the files themselves are still used by `api/tools/job_analyzer.py`. The *node functions* in them may only be called by Phase 1 graph. Remove those imports too:
```python
from api.agents.archetype_detector import archetype_detector_node
from api.agents.legitimacy_scorer import legitimacy_scorer_node
```

- [ ] **Step 3: Remove GRAPH_NODE_ORDER**

Remove the entire `GRAPH_NODE_ORDER` list (lines 28-43).

- [ ] **Step 4: Remove Phase-1-only state fields from AgentState**

Remove these fields from `AgentState` TypedDict that are Phase-1-specific:
- `external_evidence_pack` — Phase 1 field, Phase 2 uses `job_snapshot`
- `query_pack` — Phase 1 field
- `fact_check_report` — Phase 1 field
- `retrieval_diagnostics` — Phase 1 field (Phase 2 uses `insights`)
- `adaptive_framing` — Phase 1 career-ops field
- `gap_analysis` — Phase 1 field
- `level_strategy` — Phase 1 field
- `score_interpretation` — Phase 1 field

Also remove from `build_initial_state()` the initialization of these fields.

- [ ] **Step 5: Remove Phase 1 helper functions**

Remove:
- `_parse_review_feedback()` function
- `route_after_review()` function
- `build_career_research_graph()` function (the entire function)

- [ ] **Step 6: Remove Phase 1 `build_agent_message_event` cases**

In `build_agent_message_event()`, remove the cases for:
- `"IntentRouterNode"`, `"SearchAgent"`, `"JobIntelligenceAgent"`, `"MatchingAgent"`, `"ResumeTailorAgent"`, `"QueryAgent"`, `"InsightAgent"`, `"QualityGate"`, `"ReviewAgent"`

- [ ] **Step 7: Rename `build_phase2_graph` to `build_graph`**

```python
def build_graph() -> Any:
    """Build the workflow-based graph with Supervisor routing."""
    ...  # (same body as build_phase2_graph)
```

- [ ] **Step 8: Update `__all__` exports**

```python
__all__ = [
    "AgentState",
    "PHASE2_NODE_ORDER",
    "PHASE2_WORKFLOWS",
    "build_graph",
    "build_initial_state",
    "merge_state_update",
    "route_after_supervisor",
    "route_after_memory_retrieval",
    "route_after_matching_engine",
    "route_after_gate",
]
```

- [ ] **Step 9: Run Phase 2 connectivity tests**

Run: `python -m pytest tests/test_phase2_connectivity.py tests/test_phase3_connectivity.py tests/test_phase4_connectivity.py tests/test_phase5_connectivity.py -v`
Expected: All pass

- [ ] **Step 10: Commit**

```bash
git add api/core/graph.py
git commit -m "refactor: remove Phase 1 graph, make Phase 2 the sole graph"
```

---

### Task 2: Simplify main.py

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Read current main.py**

Read `api/main.py` to understand the current Phase 1/Phase 2 dual setup.

- [ ] **Step 2: Remove `_graph` global and simplify `_get_graph()`**

Replace:
```python
_graph = build_career_research_graph()
_phase2_graph = None

def _get_graph(phase: str = "1") -> Any:
    if phase == "2":
        global _phase2_graph
        if _phase2_graph is None:
            _phase2_graph = build_phase2_graph()
        return _phase2_graph
    return _graph
```

With:
```python
_graph = None

def _get_graph() -> Any:
    global _graph
    if _graph is None:
        from api.core.graph import build_graph
        _graph = build_graph()
    return _graph
```

Update the import at the top of the file:
```python
# Remove: from api.core.graph import build_career_research_graph, ...
# Replace with: from api.core.graph import build_graph, build_initial_state, ...
```
Actually, main.py imports graph-related things. Let me check what it imports and fix accordingly.

- [ ] **Step 3: Remove `phase` from request models**

Find `ResearchRequest`, `ResearchCaseRunRequest`, `EvalRunRequest` and remove the `phase` field.

- [ ] **Step 4: Update all `_get_graph(phase=...)` calls to `_get_graph()`**

Find all call sites of `_get_graph(payload.phase or "2")` etc. and change to `_get_graph()`.

- [ ] **Step 5: Run API tests**

Run: `python -m pytest tests/test_research_api.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add api/main.py
git commit -m "refactor: remove phase switching, Phase 2 is sole runtime"
```

---

### Task 3: Delete Dead Agent Files

**Files:**
- Delete: 8 files in `api/agents/`

- [ ] **Step 1: Delete the 8 dead agent files**

```bash
git rm api/agents/intent_router.py
git rm api/agents/insight_agent.py
git rm api/agents/job_intelligence_agent.py
git rm api/agents/matching_agent.py
git rm api/agents/quality_gate.py
git rm api/agents/query_agent.py
git rm api/agents/review_agent.py
git rm api/agents/offer_evaluator.py
```

- [ ] **Step 2: Run full test suite to verify nothing broken**

Run: `python -m pytest tests/ -q`
Expected: All pass (these files should have no remaining importers)

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: remove 8 dead Phase 1 agent files"
```

---

### Task 4: Integration Verification

**Files:**
- All (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All passing, no regressions

- [ ] **Step 2: Verify imports are clean**

```bash
python -c "from api.core.graph import build_graph; print('graph OK')"
python -c "from api.main import app; print('app OK')"
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: Phase 6 integration verification complete"
```

---

## Self-Review Checklist

### Spec Coverage
This is a cleanup phase — no new features. It removes tech debt that was noted in the initial exploration.

### Placeholder Scan
No TBD, TODO, or vague references.

### Type Consistency
- `build_graph()` replaces both `build_career_research_graph()` and `build_phase2_graph()` — same return type
- `_get_graph()` no longer takes a `phase` parameter — all call sites updated
- Deleted files have no remaining importers in the codebase
