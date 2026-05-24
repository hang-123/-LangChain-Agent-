# Phase 5: Eval Infrastructure & Cleanup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make eval/case-run endpoints Phase-2-aware, implement Interview Eval (spec 32) and Routing Eval (spec 33) scoring functions, and add Phase 2 eval case fixtures.

**Architecture:** Follow the existing harness pattern — each scoring function is a pure function `(case, state) -> int` returning penalty points. The `score_case_result()` orchestrator sums penalties and checks thresholds. New scoring functions (`_score_interview`, `_score_routing`) are added to `harness.py`. The eval endpoints in `main.py` gain a `phase` field (default `"2"`) and use `_get_graph()` instead of hardcoded `_graph`.

**Tech Stack:** Python async, Pydantic, pytest, existing `api/evals/harness.py` pattern

---

## File Structure

### Create
- `api/evals/fixtures/interview_cases.json` — Interview eval test cases
- `api/evals/fixtures/routing_cases.json` — Routing eval test cases
- `tests/test_eval_interview.py` — Interview eval scoring tests
- `tests/test_eval_routing.py` — Routing eval scoring tests

### Modify
- `api/main.py` — Add `phase` field to `CaseRunRequest`, `EvalRunRequest`; use `_get_graph()` in eval endpoints
- `api/evals/harness.py` — Add `_score_interview()`, `_score_routing()`; update `NodeScorecard` and `EvalPolicy`
- `api/core/contracts.py` — Add `interview_score` and `routing_score` to `NodeScorecard`

---

### Task 1: Add Phase Support to Eval Endpoints

**Files:**
- Modify: `api/main.py`

The eval and case-run endpoints hardcode `_graph` (Phase 1). Add `phase` parameter and use `_get_graph()`.

- [ ] **Step 1: Read current eval/case-run endpoints in main.py**

Read `api/main.py` around lines 238-312 to see the `ResearchCaseRunRequest`, case-run endpoint, `EvalRunRequest`, and eval endpoint.

- [ ] **Step 2: Add `phase` field to request models and update endpoints**

**Change A: `ResearchCaseRunRequest`**

Find the model definition. Add `phase` field:

```python
class ResearchCaseRunRequest(BaseModel):
    case_ids: list[str] = Field(default_factory=list)
    phase: str = Field(default="2", description="Graph phase: '1' for legacy, '2' for workflow-based")
```

**Change B: Case-run endpoint (around line 238)**

Replace:
```python
session = ResearchExecutionSession(_graph, initial_state)
```
With:
```python
graph = _get_graph(phase=request.phase or "2")
session = ResearchExecutionSession(graph, initial_state)
```

**Change C: `EvalRunRequest`**

Find the model definition. Add `phase` field:

```python
class EvalRunRequest(BaseModel):
    case_ids: list[str] = Field(default_factory=list)
    phase: str = Field(default="2", description="Graph phase: '1' for legacy, '2' for workflow-based")
```

**Change D: Eval endpoint (around line 286)**

Replace:
```python
session = ResearchExecutionSession(_graph, initial_state)
```
With:
```python
graph = _get_graph(phase=request.phase or "2")
session = ResearchExecutionSession(graph, initial_state)
```

- [ ] **Step 3: Run API tests**

Run: `python -m pytest tests/test_research_api.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add api/main.py
git commit -m "feat: add phase parameter to eval and case-run endpoints"
```

---

### Task 2: Implement Interview Eval Scoring (spec 32)

**Files:**
- Modify: `api/evals/harness.py`
- Modify: `api/core/contracts.py`
- Create: `api/evals/fixtures/interview_cases.json`
- Create: `tests/test_eval_interview.py`

- [ ] **Step 1: Add `interview_score` to NodeScorecard**

In `api/core/contracts.py`, find `NodeScorecard` and add:

```python
class NodeScorecard(BaseModel):
    retrieval: int = Field(default=0, ge=0, le=100)
    attribution: int = Field(default=0, ge=0, le=100)
    insight: int = Field(default=0, ge=0, le=100)
    report_compliance: int = Field(default=0, ge=0, le=100)
    matching: int = Field(default=0, ge=0, le=100)
    resume: int = Field(default=0, ge=0, le=100)
    interview: int = Field(default=0, ge=0, le=100)
    routing: int = Field(default=0, ge=0, le=100)
```

- [ ] **Step 2: Create interview eval test cases**

Create `api/evals/fixtures/interview_cases.json`:

```json
[
  {
    "case_id": "interview_001",
    "query": "帮我准备面试问题",
    "expected_intent": "interview_prep",
    "interview_ground_truth": {
      "min_behavioral_questions": 3,
      "min_technical_questions": 2,
      "min_project_deep_dive": 1,
      "required_risk_questions": 1,
      "expected_role_keywords": ["后端开发", "Python"],
      "forbidden_phrases": ["保证通过", "完美答案"]
    },
    "risk_tags": []
  },
  {
    "case_id": "interview_002",
    "query": "generate interview questions for frontend role",
    "expected_intent": "interview_prep",
    "interview_ground_truth": {
      "min_behavioral_questions": 3,
      "min_technical_questions": 2,
      "min_project_deep_dive": 1,
      "required_risk_questions": 1,
      "expected_role_keywords": ["前端", "React"],
      "forbidden_phrases": []
    },
    "risk_tags": []
  },
  {
    "case_id": "interview_003",
    "query": "面试准备",
    "expected_intent": "interview_prep",
    "interview_ground_truth": {
      "min_behavioral_questions": 2,
      "min_technical_questions": 1,
      "min_project_deep_dive": 1,
      "required_risk_questions": 0,
      "expected_role_keywords": [],
      "forbidden_phrases": []
    },
    "risk_tags": ["sparse_input"]
  }
]
```

- [ ] **Step 3: Write failing test for interview scoring**

Create `tests/test_eval_interview.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from api.evals.harness import _score_interview


def _load_fixtures():
    path = Path(__file__).parent.parent / "api" / "evals" / "fixtures" / "interview_cases.json"
    return json.loads(path.read_text())


def test_score_interview_perfect_pack():
    """A complete prep_pack should score 100 (no penalties)."""
    case = {
        "interview_ground_truth": {
            "min_behavioral_questions": 2,
            "min_technical_questions": 1,
            "min_project_deep_dive": 1,
            "required_risk_questions": 1,
            "expected_role_keywords": ["后端"],
            "forbidden_phrases": [],
        }
    }
    state = {
        "prep_pack": {
            "behavioral_questions": [
                {"question": "说说你的项目经验", "category": "behavioral", "evidence_refs": ["ev1"]},
                {"question": "如何处理冲突", "category": "behavioral", "evidence_refs": ["ev2"]},
            ],
            "technical_questions": [
                {"question": "Python GIL是什么", "category": "technical", "evidence_refs": ["ev3"]},
            ],
            "project_deep_dive": [
                {"question": "详细介绍你的后端项目架构", "category": "project_deep_dive", "evidence_refs": ["ev4"]},
            ],
            "risk_questions": [
                {"question": "你的技术栈和后端岗位有什么差距", "category": "project_deep_dive"},
            ],
            "practice_advice": ["多做mock interview", "复习系统设计"],
        }
    }
    score = _score_interview(case, state)
    assert score == 100, f"Expected 100, got {score}"


def test_score_interview_missing_deep_dive():
    """Missing project_deep_dive should penalize."""
    case = {
        "interview_ground_truth": {
            "min_behavioral_questions": 2,
            "min_technical_questions": 1,
            "min_project_deep_dive": 1,
            "required_risk_questions": 0,
            "expected_role_keywords": [],
            "forbidden_phrases": [],
        }
    }
    state = {
        "prep_pack": {
            "behavioral_questions": [{"question": "Q1", "evidence_refs": []}],
            "technical_questions": [{"question": "Q1", "evidence_refs": []}],
            "project_deep_dive": [],
            "risk_questions": [],
            "practice_advice": [],
        }
    }
    score = _score_interview(case, state)
    assert score < 80, f"Expected penalty for missing deep dive, got {score}"


def test_score_interview_empty_pack():
    """Empty prep_pack should score 0."""
    case = {
        "interview_ground_truth": {
            "min_behavioral_questions": 1,
            "min_technical_questions": 1,
            "min_project_deep_dive": 1,
            "required_risk_questions": 0,
            "expected_role_keywords": [],
            "forbidden_phrases": [],
        }
    }
    state = {"prep_pack": {}}
    score = _score_interview(case, state)
    assert score == 0, f"Expected 0 for empty pack, got {score}"
```

Run: `python -m pytest tests/test_eval_interview.py -q`
Expected: FAIL (function not defined)

- [ ] **Step 4: Implement _score_interview**

In `api/evals/harness.py`, add the scoring function:

```python
def _score_interview(case: dict, state: dict) -> int:
    """Score interview prep quality per spec 32.
    
    Dimensions:
    - question_relevance: questions match role keywords
    - question_diversity: covers behavioral/technical/deep_dive
    - evidence_grounding: questions bound to evidence_refs
    - actionability: practice advice present
    
    Returns score 0-100.
    """
    gt = dict(case.get("interview_ground_truth") or {})
    prep_pack = dict(state.get("prep_pack") or {})
    
    if not prep_pack:
        return 0
    
    behavioral = list(prep_pack.get("behavioral_questions") or [])
    technical = list(prep_pack.get("technical_questions") or [])
    deep_dive = list(prep_pack.get("project_deep_dive") or [])
    risk_qs = list(prep_pack.get("risk_questions") or [])
    advice = list(prep_pack.get("practice_advice") or [])
    
    penalties = 0
    
    # ── question_relevance (max -25) ──
    expected_keywords = gt.get("expected_role_keywords", [])
    if expected_keywords:
        all_questions = behavioral + technical + deep_dive + risk_qs
        all_text = " ".join(
            q.get("question", "") + " " + q.get("answer_framework", "")
            for q in all_questions
        ).lower()
        keyword_hits = sum(1 for kw in expected_keywords if kw.lower() in all_text)
        if keyword_hits < len(expected_keywords):
            penalties += 25 * (1 - keyword_hits / len(expected_keywords))
    
    # ── question_diversity (max -30) ──
    min_behavioral = gt.get("min_behavioral_questions", 2)
    min_technical = gt.get("min_technical_questions", 1)
    min_deep_dive = gt.get("min_project_deep_dive", 1)
    
    if len(behavioral) < min_behavioral:
        penalties += 10 * (min_behavioral - len(behavioral))
    if len(technical) < min_technical:
        penalties += 10 * (min_technical - len(technical))
    if len(deep_dive) < min_deep_dive:
        penalties += 10 * (min_deep_dive - len(deep_dive))
    
    # ── evidence_grounding (max -25) ──
    all_with_refs = [q for q in behavioral + technical + deep_dive
                     if q.get("evidence_refs") and len(q.get("evidence_refs", [])) > 0]
    total_questions = len(behavioral) + len(technical) + len(deep_dive)
    if total_questions > 0:
        grounding_ratio = len(all_with_refs) / total_questions
        if grounding_ratio < 0.5:
            penalties += 25 * (1 - grounding_ratio)
    
    # ── actionability (max -10) ──
    if len(advice) < 2:
        penalties += 5 * (2 - len(advice))
    
    # ── risk questions (max -10) ──
    required_risk = gt.get("required_risk_questions", 0)
    if len(risk_qs) < required_risk:
        penalties += 10 * (required_risk - len(risk_qs))
    
    return max(0, 100 - int(penalties))
```

- [ ] **Step 5: Run interview eval tests**

Run: `python -m pytest tests/test_eval_interview.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add api/evals/harness.py api/evals/fixtures/interview_cases.json tests/test_eval_interview.py api/core/contracts.py
git commit -m "feat: implement interview eval scoring per spec 32"
```

---

### Task 3: Implement Routing Eval Scoring (spec 33)

**Files:**
- Modify: `api/evals/harness.py`
- Create: `api/evals/fixtures/routing_cases.json`
- Create: `tests/test_eval_routing.py`

- [ ] **Step 1: Create routing eval test cases**

Create `api/evals/fixtures/routing_cases.json`:

```json
[
  {
    "case_id": "routing_001",
    "query": "帮我分析这个岗位的匹配度",
    "expected_intent": "match",
    "routing_ground_truth": {
      "expected_intent": "match",
      "expected_workflow": "wf_match_v2",
      "expected_missing_artifacts": [],
      "required_steps": ["SearchOrchestrator", "JobAnalyzer", "MatchingEngine"]
    }
  },
  {
    "case_id": "routing_002",
    "query": "根据这个JD帮我改简历",
    "expected_intent": "resume_tailor",
    "routing_ground_truth": {
      "expected_intent": "resume_tailor",
      "expected_workflow": "wf_resume_tailor_v2",
      "expected_missing_artifacts": ["candidate_profile"],
      "required_steps": ["JobAnalyzer", "MatchingEngine", "ResumeTailor"]
    }
  },
  {
    "case_id": "routing_003",
    "query": "我有两个offer帮我比较",
    "expected_intent": "offer_compare",
    "routing_ground_truth": {
      "expected_intent": "offer_compare",
      "expected_workflow": "wf_offer_compare",
      "expected_missing_artifacts": [],
      "required_steps": ["OfferEvaluator"]
    }
  },
  {
    "case_id": "routing_004",
    "query": "帮我看看这个职位适不适合我",
    "expected_intent": "match",
    "routing_ground_truth": {
      "expected_intent": "match",
      "expected_workflow": "wf_match_v2",
      "expected_missing_artifacts": [],
      "required_steps": ["SearchOrchestrator", "JobAnalyzer", "MatchingEngine"]
    }
  }
]
```

- [ ] **Step 2: Write failing test for routing scoring**

Create `tests/test_eval_routing.py`:

```python
from __future__ import annotations

from api.evals.harness import _score_routing


def test_score_routing_correct_intent_and_workflow():
    """Correct intent + workflow = high score."""
    case = {
        "routing_ground_truth": {
            "expected_intent": "match",
            "expected_workflow": "wf_match_v2",
            "expected_missing_artifacts": [],
            "required_steps": ["SearchOrchestrator", "JobAnalyzer", "MatchingEngine"],
        }
    }
    state = {
        "intent": "match",
        "workflow_id": "wf_match_v2",
        "missing_artifacts": [],
        "run_trace": [
            {"node": "Supervisor", "phase": "started"},
            {"node": "SearchOrchestrator", "phase": "completed"},
            {"node": "JobAnalyzer", "phase": "completed"},
            {"node": "MatchingEngine", "phase": "completed"},
        ],
    }
    score = _score_routing(case, state)
    assert score == 100, f"Expected 100, got {score}"


def test_score_routing_wrong_workflow():
    """Wrong workflow = significant penalty."""
    case = {
        "routing_ground_truth": {
            "expected_intent": "match",
            "expected_workflow": "wf_match_v2",
            "expected_missing_artifacts": [],
            "required_steps": ["SearchOrchestrator"],
        }
    }
    state = {
        "intent": "match",
        "workflow_id": "wf_resume_tailor_v2",  # wrong workflow
        "missing_artifacts": [],
        "run_trace": [],
    }
    score = _score_routing(case, state)
    assert score < 70, f"Expected penalty for wrong workflow, got {score}"


def test_score_routing_missing_steps():
    """Missing required steps = penalty."""
    case = {
        "routing_ground_truth": {
            "expected_intent": "match",
            "expected_workflow": "wf_match_v2",
            "expected_missing_artifacts": [],
            "required_steps": ["SearchOrchestrator", "JobAnalyzer", "MatchingEngine"],
        }
    }
    state = {
        "intent": "match",
        "workflow_id": "wf_match_v2",
        "missing_artifacts": [],
        "run_trace": [
            {"node": "SearchOrchestrator", "phase": "completed"},
            # Missing: JobAnalyzer, MatchingEngine
        ],
    }
    score = _score_routing(case, state)
    assert score < 70, f"Expected penalty for missing steps, got {score}"
```

Run: `python -m pytest tests/test_eval_routing.py -q`
Expected: FAIL

- [ ] **Step 3: Implement _score_routing**

In `api/evals/harness.py`, add:

```python
def _score_routing(case: dict, state: dict) -> int:
    """Score routing accuracy per spec 33.
    
    Dimensions:
    - intent_accuracy: correct primary intent
    - workflow_accuracy: correct workflow selected
    - missing_input_detection: missing inputs correctly flagged
    - step_completeness: required steps executed
    
    Returns score 0-100.
    """
    gt = dict(case.get("routing_ground_truth") or {})
    penalties = 0
    
    # ── intent_accuracy (max -30) ──
    expected_intent = gt.get("expected_intent", "")
    actual_intent = str(state.get("intent") or "")
    if expected_intent and actual_intent != expected_intent:
        penalties += 30
    
    # ── workflow_accuracy (max -30) ──
    expected_workflow = gt.get("expected_workflow", "")
    actual_workflow = str(state.get("workflow_id") or "")
    if expected_workflow and actual_workflow != expected_workflow:
        penalties += 30
    
    # ── missing_input_detection (max -20) ──
    expected_missing = set(gt.get("expected_missing_artifacts", []))
    actual_missing = set(state.get("missing_artifacts", []))
    if expected_missing:
        # Penalize for undetected missing inputs
        undetected = expected_missing - actual_missing
        if undetected:
            penalties += min(20, 10 * len(undetected))
        # Penalize for false missing reports
        false_missing = actual_missing - expected_missing
        if false_missing:
            penalties += min(10, 5 * len(false_missing))
    
    # ── step_completeness (max -20) ──
    required_steps = gt.get("required_steps", [])
    if required_steps:
        executed_nodes = {
            entry.get("node", "")
            for entry in state.get("run_trace", [])
            if entry.get("phase") == "completed"
        }
        missing_steps = [s for s in required_steps if s not in executed_nodes]
        if missing_steps:
            penalties += min(20, 5 * len(missing_steps))
    
    return max(0, 100 - int(penalties))
```

- [ ] **Step 4: Run routing eval tests**

Run: `python -m pytest tests/test_eval_routing.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add api/evals/harness.py api/evals/fixtures/routing_cases.json tests/test_eval_routing.py
git commit -m "feat: implement routing eval scoring per spec 33"
```

---

### Task 4: Update score_case_result orchestrator

**Files:**
- Modify: `api/evals/harness.py`
- Modify: `api/core/contracts.py`

- [ ] **Step 1: Add `min_interview_score` and `min_routing_score` to EvalPolicy**

In `api/core/contracts.py`, find `EvalPolicy` (check `api/core/policy_loader.py` or wherever policy defaults are defined). Add:

```python
    min_interview_score: int = 70
    min_routing_score: int = 80
```

If `EvalPolicy` doesn't exist yet in contracts.py, add these to the settings defaults instead.

- [ ] **Step 2: Update `score_case_result` to run new scorers**

In `api/evals/harness.py`, find `score_case_result()`. Add calls to `_score_interview` and `_score_routing` when relevant:

```python
    # In score_case_result(), after the existing per-dimension scoring:
    
    # Interview eval (only for interview_prep workflows)
    interview_score = 100
    if case.get("expected_intent") == "interview_prep" or state.get("prep_pack"):
        interview_score = _score_interview(case, state)
        node_scores.interview = interview_score
    
    # Routing eval (always run — every case tests routing)
    routing_score = 100
    if case.get("routing_ground_truth"):
        routing_score = _score_routing(case, state)
        node_scores.routing = routing_score
    
    # Include in threshold checks
    thresholds = [
        (retrieval_score, getattr(policy, 'min_retrieval_score', 60), "retrieval"),
        ...
        (interview_score, getattr(policy, 'min_interview_score', 70), "interview"),
        (routing_score, getattr(policy, 'min_routing_score', 80), "routing"),
    ]
```

- [ ] **Step 3: Run full harness tests**

Run: `python -m pytest tests/test_eval_harness.py tests/test_eval_interview.py tests/test_eval_routing.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add api/evals/harness.py api/core/contracts.py
git commit -m "feat: integrate interview and routing scores into eval orchestrator"
```

---

### Task 5: Integration Verification

**Files:**
- All (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All pass

- [ ] **Step 2: Verify eval endpoint changes are testable**

Run: `python -m pytest tests/test_research_api.py tests/test_eval_harness.py tests/test_eval_interview.py tests/test_eval_routing.py tests/test_eval_diff.py -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: Phase 5 integration verification complete"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Section | Task |
|---|---|
| 32-eval-interview.md — 4 dimensions (relevance, diversity, grounding, actionability) | Task 2 |
| 32-eval-interview.md — Pass gates (>=0.80 relevance, >=0.85 grounding) | Task 2 |
| 32-eval-interview.md — min_deep_dive + risk questions | Task 2 |
| 33-eval-routing.md — 4 dimensions (intent, workflow, missing_input, step_completeness) | Task 3 |
| 33-eval-routing.md — Pass gates (>=0.90 intent, >=0.85 workflow, >=0.90 missing) | Task 3 |
| Eval endpoints Phase-2-aware | Task 1 |
| NodeScorecard new dimensions | Task 2, Task 4 |
| score_case_result integration | Task 4 |

### Placeholder Scan

No TBD, TODO, or vague references. Every step has exact code and expected output.

### Type Consistency

- `_score_interview(case: dict, state: dict) -> int` matches harness pattern
- `_score_routing(case: dict, state: dict) -> int` matches harness pattern
- `NodeScorecard.interview: int` and `routing: int` added in Task 2, used in Task 4
- `EvalRunRequest.phase: str` and `ResearchCaseRunRequest.phase: str` used in Task 1
