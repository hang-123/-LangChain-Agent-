from __future__ import annotations

import os
import uuid

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
    assert result.get("error_code") == "duplicate"
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


@pytest.mark.asyncio
async def test_run_application_store_create():
    from api.tools.application_store import run_application_store
    import os, uuid
    db_path = "data/application_store.db"
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        uid = uuid.uuid4().hex[:8]
        state = {
            "application_store_request": {
                "operation": "create_application",
                "payload": {"candidate_id": f"c_{uid}", "job_id": f"j_{uid}", "company": "Co", "role": "Dev", "status": "planned"},
            }
        }
        result = await run_application_store(state)
        resp = result["application_store_response"]
        assert resp["ok"] is True
        assert resp["application_record"]["candidate_id"] == f"c_{uid}"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.asyncio
async def test_run_application_store_invalid_request():
    from api.tools.application_store import run_application_store
    result = await run_application_store({})
    resp = result["application_store_response"]
    assert resp["ok"] is False
    assert resp["error_code"] == "invalid_request"


@pytest.mark.asyncio
async def test_run_application_store_unknown_operation():
    from api.tools.application_store import run_application_store
    state = {
        "application_store_request": {
            "operation": "nonexistent_op",
            "payload": {},
        }
    }
    result = await run_application_store(state)
    resp = result["application_store_response"]
    assert resp["ok"] is False
    assert resp["error_code"] == "unknown_operation"
