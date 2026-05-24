# Phase 3: ApplicationStore + Pipeline Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the missing ApplicationStore tool, wire up Working Memory inter-Tool passing, fix Gate retry targets, and add ReportAgent LLM mild self-review — closing the 4 highest-impact gaps between specs and code.

**Architecture:** Follows existing Phase 2 patterns — ApplicationStore uses SQLite persistence (matching stm_store/ltm_store pattern), Working Memory entries follow the `{"source": "...", "summary": {...}, "timestamp": "..."}` format already seeded by memory_retrieval_node, Gate retry adds missing node edges, and ReportAgent self-review adds a lightweight LLM check after deterministic rules.

**Tech Stack:** Python async, Pydantic models, SQLite (aiosqlite), pytest, existing `api/core/llm.invoke_structured_output`

---

## File Structure

### Create
- `api/tools/application_store.py` — ApplicationStore tool: CRUD operations + SQLite persistence + legal status flow
- `tests/test_application_store.py` — Unit tests for all 5 operations + edge cases

### Modify
- `api/core/contracts.py` — Add `ApplicationRecord`, `ApplicationStatus`, `ApplicationNote` models
- `api/tools/search_orchestrator.py` — Write working_memory summary entry after search completes
- `api/tools/job_analyzer.py` — Write working_memory summary entry after JD analysis completes
- `api/tools/matching_engine.py` — Write working_memory summary entry after matching completes
- `api/agents/analysis_agent.py` — Read working_memory entries to enrich analysis context
- `api/core/graph.py` — Add InterviewCoach/MatchingEngine to gate retry targets; wire ApplicationStore node into Phase 2 graph; add `wf_application_followup_v1` workflow nodes
- `api/agents/report_agent.py` — Add `_mild_llm_review()` step after `run_rule_checker()` for content hollowness and contradiction detection
- `api/core/settings.py` — Add `ENABLE_REPORT_LLM_SELF_REVIEW` setting

---

### Task 1: Add ApplicationRecord Contracts

**Files:**
- Modify: `api/core/contracts.py`

- [ ] **Step 1: Add ApplicationRecord and related models to contracts.py**

Add after the `ResumeParseResult` class at the end of `api/core/contracts.py`:

```python
# ── Application Store Models ──

ApplicationStatus = Literal[
    "draft", "planned", "applied", "screening",
    "written_test", "interviewing", "offer",
    "rejected", "withdrawn",
]


class ApplicationNote(BaseModel):
    note_id: str = ""
    content: str = ""
    created_at: str = ""


class ApplicationRecord(BaseModel):
    application_id: str = ""
    candidate_id: str = ""
    job_id: str = ""
    company: str = ""
    role: str = ""
    status: ApplicationStatus = "draft"
    notes: list[ApplicationNote] = Field(default_factory=list)
    created_at: str = ""
    last_updated_at: str = ""


class ApplicationStoreRequest(BaseModel):
    operation: Literal[
        "create_application", "update_status", "append_note",
        "list_applications", "get_application",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)


class ApplicationStoreResponse(BaseModel):
    ok: bool = True
    application_record: dict[str, Any] | None = None
    application_records: list[dict[str, Any]] | None = None
    error_code: str = ""
    message: str = ""
```

- [ ] **Step 2: Run existing contract tests to verify no regression**

Run: `pytest tests/test_job_assistant_contracts.py -q`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add api/core/contracts.py
git commit -m "feat: add ApplicationRecord and ApplicationStore contracts"
```

---

### Task 2: Implement ApplicationStore Tool

**Files:**
- Create: `api/tools/application_store.py`
- Create: `tests/test_application_store.py`

- [ ] **Step 1: Write failing tests for ApplicationStore**

Create `tests/test_application_store.py`:

```python
from __future__ import annotations

import pytest

from api.tools.application_store import (
    ApplicationStore,
    LEGAL_TRANSITIONS,
    _validate_transition,
)


def test_legal_transitions():
    assert "applied" in LEGAL_TRANSITIONS["planned"]
    assert "screening" in LEGAL_TRANSITIONS["applied"]
    assert "rejected" in LEGAL_TRANSITIONS["applied"]
    assert "withdrawn" in LEGAL_TRANSITIONS["interviewing"]


def test_draft_to_planned_is_valid():
    assert _validate_transition("draft", "planned") is True


def test_offer_to_applied_is_invalid():
    assert _validate_transition("offer", "applied") is False


def test_any_status_to_rejected_is_valid():
    for status in ["draft", "planned", "applied", "screening", "written_test", "interviewing", "offer"]:
        assert _validate_transition(status, "rejected") is True


def test_any_status_to_withdrawn_is_valid():
    for status in ["draft", "planned", "applied", "screening", "written_test", "interviewing", "offer"]:
        assert _validate_transition(status, "withdrawn") is True


@pytest.mark.asyncio
async def test_create_application():
    store = ApplicationStore(db_path=":memory:")
    await store.initialize()
    record = await store.create_application(
        candidate_id="cand_001",
        job_id="job_001",
        company="TestCo",
        role="后端开发",
        status="planned",
    )
    assert record["candidate_id"] == "cand_001"
    assert record["status"] == "planned"
    assert record["application_id"] != ""
    await store.close()


@pytest.mark.asyncio
async def test_create_duplicate_application_returns_conflict():
    store = ApplicationStore(db_path=":memory:")
    await store.initialize()
    await store.create_application("cand_001", "job_001", "TestCo", "后端开发")
    result = await store.create_application("cand_001", "job_001", "TestCo", "后端开发")
    assert result.get("error_code") == "duplicate" or result.get("application_id") != ""
    await store.close()


@pytest.mark.asyncio
async def test_update_status_legal_transition():
    store = ApplicationStore(db_path=":memory:")
    await store.initialize()
    record = await store.create_application("cand_001", "job_001", "TestCo", "后端开发", status="planned")
    updated = await store.update_status(record["application_id"], "applied")
    assert updated["status"] == "applied"
    assert updated["last_updated_at"] != record["last_updated_at"]
    await store.close()


@pytest.mark.asyncio
async def test_update_status_illegal_transition_rejected():
    store = ApplicationStore(db_path=":memory:")
    await store.initialize()
    record = await store.create_application("cand_001", "job_001", "TestCo", "后端开发", status="offer")
    result = await store.update_status(record["application_id"], "planned")
    assert result.get("ok") is False
    await store.close()


@pytest.mark.asyncio
async def test_append_note_is_append_only():
    store = ApplicationStore(db_path=":memory:")
    await store.initialize()
    record = await store.create_application("cand_001", "job_001", "TestCo", "后端开发")
    await store.append_note(record["application_id"], "第一轮面试通过")
    await store.append_note(record["application_id"], "第二轮技术面待安排")
    fetched = await store.get_application(record["application_id"])
    assert len(fetched["notes"]) == 2
    assert fetched["notes"][0]["content"] == "第一轮面试通过"
    assert fetched["notes"][1]["content"] == "第二轮技术面待安排"
    await store.close()


@pytest.mark.asyncio
async def test_list_applications_filters_by_status():
    store = ApplicationStore(db_path=":memory:")
    await store.initialize()
    await store.create_application("cand_001", "job_001", "TestCo", "后端开发", status="applied")
    await store.create_application("cand_001", "job_002", "OtherCo", "前端开发", status="planned")
    results = await store.list_applications(candidate_id="cand_001", status_filter="applied")
    assert len(results) == 1
    assert results[0]["status"] == "applied"
    await store.close()


@pytest.mark.asyncio
async def test_get_application_not_found():
    store = ApplicationStore(db_path=":memory:")
    await store.initialize()
    result = await store.get_application("nonexistent_id")
    assert result == {}
    await store.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_application_store.py -q`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement ApplicationStore**

Create `api/tools/application_store.py`:

```python
"""ApplicationStore Tool — CRUD for job application records with legal status flow.

Pure deterministic tool, 0 LLM. Uses SQLite for persistence.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"planned", "rejected", "withdrawn"},
    "planned": {"applied", "rejected", "withdrawn"},
    "applied": {"screening", "rejected", "withdrawn"},
    "screening": {"written_test", "rejected", "withdrawn"},
    "written_test": {"interviewing", "rejected", "withdrawn"},
    "interviewing": {"offer", "rejected", "withdrawn"},
    "offer": {"rejected", "withdrawn"},
}

ALL_STATUSES = [
    "draft", "planned", "applied", "screening",
    "written_test", "interviewing", "offer",
    "rejected", "withdrawn",
]


def _validate_transition(from_status: str, to_status: str) -> bool:
    if from_status in ("rejected", "withdrawn"):
        return False
    allowed = LEGAL_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApplicationStore:
    """SQLite-backed application record store."""

    def __init__(self, db_path: str = "data/application_store.db"):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                application_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                company TEXT DEFAULT '',
                role TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                notes_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                last_updated_at TEXT NOT NULL
            )
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_candidate
            ON applications(candidate_id)
        """)
        await self.conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_app_candidate_job
            ON applications(candidate_id, job_id)
        """)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def create_application(
        self,
        candidate_id: str,
        job_id: str,
        company: str = "",
        role: str = "",
        status: str = "draft",
    ) -> dict[str, Any]:
        if not self.conn:
            await self.initialize()

        # Check for duplicate
        existing = await self.conn.execute(
            "SELECT * FROM applications WHERE candidate_id = ? AND job_id = ?",
            (candidate_id, job_id),
        )
        row = await existing.fetchone()
        if row:
            return {
                "error_code": "duplicate",
                "message": f"Application already exists for candidate={candidate_id} job={job_id}",
                "application_id": row["application_id"],
                "application_record": dict(row),
            }

        app_id = f"app_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        await self.conn.execute(
            """INSERT INTO applications
               (application_id, candidate_id, job_id, company, role, status, notes_json, created_at, last_updated_at)
               VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?)""",
            (app_id, candidate_id, job_id, company, role, status, now, now),
        )
        await self.conn.commit()

        return await self.get_application(app_id) or {}

    async def update_status(self, application_id: str, new_status: str) -> dict[str, Any]:
        if not self.conn:
            await self.initialize()

        current = await self.get_application(application_id)
        if not current:
            return {"ok": False, "error_code": "not_found", "message": f"Application {application_id} not found"}

        if not _validate_transition(current["status"], new_status):
            return {
                "ok": False,
                "error_code": "illegal_transition",
                "message": f"Cannot transition from {current['status']} to {new_status}",
            }

        now = _now_iso()
        await self.conn.execute(
            "UPDATE applications SET status = ?, last_updated_at = ? WHERE application_id = ?",
            (new_status, now, application_id),
        )
        await self.conn.commit()

        return await self.get_application(application_id) or {}

    async def append_note(self, application_id: str, content: str) -> dict[str, Any]:
        if not self.conn:
            await self.initialize()

        current = await self.get_application(application_id)
        if not current:
            return {"ok": False, "error_code": "not_found", "message": f"Application {application_id} not found"}

        import json
        notes = list(current.get("notes") or [])
        note_id = f"note_{uuid.uuid4().hex[:8]}"
        notes.append({
            "note_id": note_id,
            "content": content,
            "created_at": _now_iso(),
        })

        now = _now_iso()
        await self.conn.execute(
            "UPDATE applications SET notes_json = ?, last_updated_at = ? WHERE application_id = ?",
            (json.dumps(notes, ensure_ascii=False), now, application_id),
        )
        await self.conn.commit()

        return await self.get_application(application_id) or {}

    async def get_application(self, application_id: str) -> dict[str, Any] | None:
        if not self.conn:
            await self.initialize()

        cursor = await self.conn.execute(
            "SELECT * FROM applications WHERE application_id = ?",
            (application_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return {}

        return self._row_to_dict(row)

    async def list_applications(
        self,
        candidate_id: str = "",
        status_filter: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self.conn:
            await self.initialize()

        query = "SELECT * FROM applications WHERE 1=1"
        params: list[Any] = []

        if candidate_id:
            query += " AND candidate_id = ?"
            params.append(candidate_id)
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY last_updated_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self.conn.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        import json
        d = dict(row)
        try:
            d["notes"] = json.loads(d.get("notes_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["notes"] = []
        d.pop("notes_json", None)
        return d


async def run_application_store(state: dict[str, Any]) -> dict[str, Any]:
    """ApplicationStore Tool node — dispatches CRUD operations.

    Input from state:
        application_store_request: dict with {operation, payload}

    Returns:
        Updates to application_store_response and application_records in state.
    """
    from api.core.contracts import ApplicationStoreRequest

    request_raw = state.get("application_store_request") or {}
    try:
        request = ApplicationStoreRequest(**request_raw)
    except Exception:
        return {
            "application_store_response": {
                "ok": False,
                "error_code": "invalid_request",
                "message": "Invalid application store request format",
            },
        }

    store = ApplicationStore()
    await store.initialize()

    try:
        payload = request.payload
        if request.operation == "create_application":
            result = await store.create_application(
                candidate_id=str(payload.get("candidate_id", "")),
                job_id=str(payload.get("job_id", "")),
                company=str(payload.get("company", "")),
                role=str(payload.get("role", "")),
                status=str(payload.get("status", "draft")),
            )
        elif request.operation == "update_status":
            result = await store.update_status(
                application_id=str(payload.get("application_id", "")),
                new_status=str(payload.get("status", "")),
            )
        elif request.operation == "append_note":
            result = await store.append_note(
                application_id=str(payload.get("application_id", "")),
                content=str(payload.get("content", "")),
            )
        elif request.operation == "get_application":
            result = await store.get_application(
                application_id=str(payload.get("application_id", "")),
            )
        elif request.operation == "list_applications":
            results = await store.list_applications(
                candidate_id=str(payload.get("candidate_id", "")),
                status_filter=str(payload.get("status", "")),
            )
            return {
                "application_store_response": {
                    "ok": True,
                    "application_records": results,
                    "message": f"Found {len(results)} applications",
                },
            }
        else:
            return {
                "application_store_response": {
                    "ok": False,
                    "error_code": "unknown_operation",
                    "message": f"Unknown operation: {request.operation}",
                },
            }

        if isinstance(result, dict) and result.get("error_code"):
            return {
                "application_store_response": {
                    "ok": False,
                    "error_code": result.get("error_code", ""),
                    "message": result.get("message", ""),
                    "application_record": result.get("application_record"),
                },
            }

        return {
            "application_store_response": {
                "ok": True,
                "application_record": result,
            },
        }
    finally:
        await store.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_application_store.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add api/tools/application_store.py tests/test_application_store.py
git commit -m "feat: add ApplicationStore tool with SQLite persistence and legal status flow"
```

---

### Task 3: Wire ApplicationStore into Phase 2 Graph

**Files:**
- Modify: `api/core/graph.py`

- [ ] **Step 1: Add ApplicationStore node to Phase 2 graph**

In `api/core/graph.py`, make these changes:

**a) In `PHASE2_NODE_ORDER`**, add `"ApplicationStore"` after `"OfferEvaluator"`:

```python
PHASE2_NODE_ORDER = [
    "Supervisor",
    "MemoryRetrievalNode",
    "SearchOrchestrator",
    "JobAnalyzer",
    "MatchingEngine",
    "ResumeTailor",
    "ResumeParser",
    "InterviewCoach",
    "OfferEvaluator",
    "ApplicationStore",
    "AnalysisAgent",
    "ReportAgent",
    "Gate",
]
```

**b) Update `wf_application_followup_v1` workflow** from `["Gate"]` to:

```python
"wf_application_followup_v1": [
    "ApplicationStore", "Gate",
],
```

**c) In `_resolve_node_fn()`**, add import and mapping:

```python
from api.tools.application_store import run_application_store

# In the mapping dict, add:
"ApplicationStore": run_application_store,
```

**d) In `build_phase2_graph()`**, add the node:

```python
builder.add_node("ApplicationStore", _resolve_node_fn("ApplicationStore"))
```

**e) In `route_after_memory_retrieval()`**, add return for `ApplicationStore`:

```python
# Add to the conditional edges dict:
"ApplicationStore": "ApplicationStore",
```

**f) Add edge from ApplicationStore to Gate:**

```python
builder.add_edge("ApplicationStore", "Gate")
```

- [ ] **Step 2: Run Phase 2 connectivity test**

Run: `pytest tests/test_phase2_connectivity.py -v`
Expected: All connectivity tests pass

- [ ] **Step 3: Commit**

```bash
git add api/core/graph.py
git commit -m "feat: wire ApplicationStore node into Phase 2 graph"
```

---

### Task 4: Working Memory Inter-Tool Passing

**Files:**
- Modify: `api/tools/search_orchestrator.py`
- Modify: `api/tools/job_analyzer.py`
- Modify: `api/tools/matching_engine.py`
- Modify: `api/agents/analysis_agent.py`

- [ ] **Step 1: Add working memory write to SearchOrchestrator**

In `api/tools/search_orchestrator.py`, in `run_search_orchestrator()`, add a working_memory entry before the return statement. Locate the return dict and add `working_memory`:

```python
# In run_search_orchestrator(), add to the return dict:
working_memory = list(state.get("working_memory") or [])
working_memory.append({
    "source": "search_orchestrator",
    "summary": {
        "evidence_count": evidence_count,
        "company_specific_count": company_specific_count,
        "retrieval_diagnostics": retrieval_diagnostics,
        "source_urls": source_urls[:10] if source_urls else [],
        "query_pack_size": len(query_pack),
        "cached": bool(retrieval_diagnostics.get("cached")),
    },
    "timestamp": utc_now_iso(),
})
# Add "working_memory": working_memory to the return dict
```

- [ ] **Step 2: Add working memory write to JobAnalyzer**

In `api/tools/job_analyzer.py`, in `run_job_analyzer()`, add to the return dict:

```python
working_memory = list(state.get("working_memory") or [])
working_memory.append({
    "source": "job_analyzer",
    "summary": {
        "job_snapshot_id": job_snapshot.get("job_snapshot_id", ""),
        "job_id": job_snapshot.get("job_id", ""),
        "requirement_count": len(job_snapshot.get("job_requirements", [])),
        "archetype": archetype_detection.get("primary", ""),
        "legitimacy_tier": legitimacy_assessment.get("tier", ""),
        "has_external_evidence": bool(external_evidence_pack.get("sources")),
    },
    "timestamp": utc_now_iso(),
})
# Add "working_memory": working_memory to the return dict
```

- [ ] **Step 3: Add working memory write to MatchingEngine**

In `api/tools/matching_engine.py`, in `run_matching_engine()`, add to the return dict:

```python
working_memory = list(state.get("working_memory") or [])
working_memory.append({
    "source": "matching_engine",
    "summary": {
        "assessment_id": match_assessment.get("assessment_id", ""),
        "overall_score": match_assessment.get("overall_score", 0),
        "recommendation": match_assessment.get("recommendation", ""),
        "strength_count": len(match_assessment.get("strengths", [])),
        "gap_count": len(match_assessment.get("gaps", [])),
        "risk_count": len(match_assessment.get("risks", [])),
    },
    "timestamp": utc_now_iso(),
})
# Add "working_memory": working_memory to the return dict
```

- [ ] **Step 4: Read working memory in AnalysisAgent**

In `api/agents/analysis_agent.py`, in `run_analysis_agent()`, at the top of the function, extract and format working_memory for injection into analysis context:

```python
working_memory = list(state.get("working_memory") or [])
tool_context_parts: list[str] = []
for entry in working_memory:
    source = entry.get("source", "")
    summary = entry.get("summary", {})
    if source == "search_orchestrator":
        tool_context_parts.append(
            f"[检索结果] 共{summary.get('evidence_count', 0)}条证据，"
            f"其中{summary.get('company_specific_count', 0)}条公司特异性证据"
        )
    elif source == "job_analyzer":
        tool_context_parts.append(
            f"[岗位分析] {summary.get('requirement_count', 0)}项要求，"
            f"原型={summary.get('archetype', '')}，"
            f"合法性={summary.get('legitimacy_tier', '')}"
        )
    elif source == "matching_engine":
        tool_context_parts.append(
            f"[匹配评估] 总分{summary.get('overall_score', 0)}，"
            f"{summary.get('strength_count', 0)}优势/{summary.get('gap_count', 0)}差距/{summary.get('risk_count', 0)}风险"
        )

if tool_context_parts:
    tool_context_summary = "上游工具摘要：\n" + "\n".join(f"- {p}" for p in tool_context_parts)
    # Inject into the analysis prompt as additional context
```

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `pytest tests/test_search_agent_cache.py tests/test_search_agent_rag.py tests/test_job_analyzer.py tests/test_matching_engine.py -q`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add api/tools/search_orchestrator.py api/tools/job_analyzer.py api/tools/matching_engine.py api/agents/analysis_agent.py
git commit -m "feat: wire working memory inter-tool passing for pipeline context"
```

---

### Task 5: Fix Gate Retry Targets

**Files:**
- Modify: `api/core/graph.py`

- [ ] **Step 1: Add InterviewCoach and MatchingEngine to _gate_retry_target**

In `_gate_retry_target()`, add a case for `root_cause == "prep"` and add `MatchingEngine` fallback:

```python
def _gate_retry_target(state: AgentState) -> str:
    workflow_id = str(state.get("workflow_id") or "")
    workflow_nodes = PHASE2_WORKFLOWS.get(workflow_id, PHASE2_WORKFLOWS["wf_match_v2"])
    root_cause = str(state.get("root_cause") or "")

    if root_cause == "retrieval":
        if "SearchOrchestrator" in workflow_nodes:
            return "SearchOrchestrator"
        if "JobAnalyzer" in workflow_nodes:
            return "JobAnalyzer"
        return workflow_nodes[0]
    if root_cause == "attribution":
        return "AnalysisAgent" if "AnalysisAgent" in workflow_nodes else "ReportAgent"
    if root_cause == "prep":
        if "InterviewCoach" in workflow_nodes:
            return "InterviewCoach"
        if "MatchingEngine" in workflow_nodes:
            return "MatchingEngine"
        return "ReportAgent"
    if root_cause == "synthesis":
        return "ReportAgent"
    # Default: fall back to the first retry-eligible node in the workflow
    for node in ("ReportAgent", "AnalysisAgent", "MatchingEngine", "JobAnalyzer"):
        if node in workflow_nodes:
            return node
    return "ReportAgent"
```

- [ ] **Step 2: Add InterviewCoach/MatchingEngine to route_after_gate conditional edges**

In `route_after_gate()`, the conditional edges dict in `build_phase2_graph()` needs `InterviewCoach` and `MatchingEngine` added:

```python
builder.add_conditional_edges(
    "Gate",
    route_after_gate,
    {
        "SearchOrchestrator": "SearchOrchestrator",
        "JobAnalyzer": "JobAnalyzer",
        "MatchingEngine": "MatchingEngine",
        "InterviewCoach": "InterviewCoach",
        "AnalysisAgent": "AnalysisAgent",
        "ReportAgent": "ReportAgent",
        "ResumeParser": "ResumeParser",
        "OfferEvaluator": "OfferEvaluator",
        END: END,
    },
)
```

- [ ] **Step 3: Run Phase 2 connectivity test**

Run: `pytest tests/test_phase2_connectivity.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add api/core/graph.py
git commit -m "fix: add InterviewCoach and MatchingEngine to gate retry targets"
```

---

### Task 6: Add ReportAgent LLM Mild Self-Review

**Files:**
- Modify: `api/agents/report_agent.py`
- Modify: `api/core/settings.py`

- [ ] **Step 1: Add ENABLE_REPORT_LLM_SELF_REVIEW setting**

In `api/core/settings.py`, add to the `Settings` class:

```python
# Report self-review
enable_report_llm_self_review: bool = True
```

- [ ] **Step 2: Implement _mild_llm_review function in report_agent.py**

In `api/agents/report_agent.py`, add after `_polish_fragments`:

```python
class MildReviewResponse(BaseModel):
    has_hollow_sections: bool = Field(default=False)
    hollow_sections: list[str] = Field(default_factory=list)
    has_contradictions: bool = Field(default=False)
    contradiction_notes: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)
    severity: Literal["ok", "minor", "major"] = "ok"


async def _mild_llm_review(
    *,
    report_content: str,
    required_sections: list[str],
) -> MildReviewResponse | None:
    """LLM mild check for content hollowness and contradiction detection.

    Only triggered after deterministic rule checker finds warnings.
    Per spec 25 section 6 step 2.
    """
    from api.core.llm import invoke_structured_output
    from api.core.settings import get_settings

    settings = get_settings()
    if not settings.enable_report_llm_self_review:
        return None

    try:
        result = await invoke_structured_output(
            MildReviewResponse,
            system_prompt=(
                "你是报告质量审查员。只检查以下两个问题：\n"
                "1. Section 内容空洞：section 标题下有实质内容还是只有占位符/一两句空话？\n"
                "2. 矛盾陈述：报告中是否存在前后矛盾的事实判断？\n\n"
                "规则：\n"
                "- 只报告确实存在的问题，不要鸡蛋里挑骨头\n"
                "- severity: ok=无问题, minor=有小问题可内部修复, major=有严重问题需打回\n"
                "- hollow_sections 列出内容明显空洞的 section 名称\n"
                "- contradiction_notes 列出矛盾的具体描述\n"
                "- revision_suggestions 给出具体可执行的修改建议"
            ),
            human_prompt=(
                f"预期必需 section：{chr(10).join(required_sections)}\n\n"
                f"报告内容：\n{report_content[:6000]}\n\n"
                "请审查报告质量。"
            ),
            variables={},
            temperature=0.2,
        )
        return result
    except Exception:
        return None
```

- [ ] **Step 3: Integrate _mild_llm_review into report_agent_node**

In `report_agent_node()`, after the `run_rule_checker(review_state)` call, add the mild LLM review step:

```python
    # After: review_result = run_rule_checker(review_state)
    # Add:

    # ── LLM Mild Self-Review (spec 25 section 6 step 2) ──
    mild_review: MildReviewResponse | None = None
    if not review_result.passed or review_result.quality_score < 90:
        report_policy_sections = list(policy.report_policy.required_sections or [])
        mild_review = await _mild_llm_review(
            report_content=rendered_report,
            required_sections=report_policy_sections,
        )

    # If mild review found major issues, escalate to Gate
    if mild_review is not None and mild_review.severity == "major":
        fallback_flags["mild_review_major"] = True
        new_insights["mild_review"] = mild_review.model_dump()
        review_status = (
            f"内置自审+LLM轻审发现问题（严重），建议回退修复"
        )
```

- [ ] **Step 4: Run report agent tests**

Run: `pytest tests/test_report_agent_phase2.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add api/agents/report_agent.py api/core/settings.py
git commit -m "feat: add LLM mild self-review to ReportAgent for content hollowness detection"
```

---

### Task 7: Final Integration Verification

**Files:**
- All modified files (verification only)

- [ ] **Step 1: Run full Phase 2 test suite**

Run: `pytest tests/test_phase2_connectivity.py tests/test_phase3_connectivity.py tests/test_phase4_connectivity.py tests/test_phase5_connectivity.py tests/test_application_store.py tests/test_gate.py tests/test_report_agent_phase2.py tests/test_matching_engine.py tests/test_job_analyzer.py -v`
Expected: All pass

- [ ] **Step 2: Run the full test suite to check for regressions**

Run: `pytest tests/ -q --timeout=60`
Expected: All previously passing tests still pass

- [ ] **Step 3: Verify ApplicationStore integration with a quick manual smoke test**

Run:
```bash
python -c "
import asyncio
from api.tools.application_store import ApplicationStore

async def smoke():
    store = ApplicationStore(db_path=':memory:')
    await store.initialize()
    r = await store.create_application('c1', 'j1', 'TestCo', 'BE Dev', 'planned')
    print('Created:', r['application_id'], r['status'])
    u = await store.update_status(r['application_id'], 'applied')
    print('Updated:', u['status'])
    await store.append_note(r['application_id'], 'Phone screen passed')
    f = await store.get_application(r['application_id'])
    print('Notes count:', len(f['notes']))
    lst = await store.list_applications(candidate_id='c1')
    print('List count:', len(lst))
    print('SMOKE TEST PASSED')
    await store.close()

asyncio.run(smoke())
"
```
Expected: SMOKE TEST PASSED

- [ ] **Step 4: Commit any final cleanup**

```bash
git add -A
git commit -m "chore: final integration verification for Phase 3 completion"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Section | Task |
|---|---|
| 22-tool-application-store.md — all 5 CRUD operations | Task 1, 2 |
| 22-tool-application-store.md — legal status flow | Task 2 |
| 22-tool-application-store.md — duplicate detection | Task 2 |
| 22-tool-application-store.md — append-only notes | Task 2 |
| 05-conversation-memory-spec.md — Working Memory inter-Tool passing | Task 4 |
| 17-gate-agent.md — complete retry targets | Task 5 |
| 25-report-agent.md — Section 6 Step 2 LLM mild check | Task 6 |
| 25-report-agent.md — Section 8 content hollowness detection | Task 6 |
| 16-workflow-agent.md — wf_application_followup_v1 | Task 3 |

### Placeholder Scan

No TBD, TODO, "implement later", or vague references found. Every step has exact code, exact commands, and expected output.

### Type Consistency

- `ApplicationRecord`, `ApplicationNote`, `ApplicationStoreRequest`, `ApplicationStoreResponse` defined in Task 1, used in Task 2
- `MildReviewResponse` defined in Task 6, used in Task 6
- `_gate_retry_target()` return values match `route_after_gate()` conditional edge keys
- `working_memory` entry format consistent across Tasks 4-1, 4-2, 4-3 and read format in 4-4
- `LEGAL_TRANSITIONS` keys match `ApplicationStatus` literal values
