from __future__ import annotations

import pytest

from api.core.conversation_memory import (
    ConversationMemorySnapshot,
    build_turn_summary,
    load_memory_for_user,
    save_memory_turn,
)


def test_build_turn_summary_uses_artifact_refs_without_full_history():
    summary = build_turn_summary(
        query="继续基于刚才的字节岗位改简历",
        state={
            "run_id": "run_001",
            "job_snapshot": {"job_snapshot_id": "js_001"},
            "match_assessment": {"assessment_id": "match_001", "recommendation": "recommended_with_risks"},
            "resume_version": {"resume_version_id": "resume_v_001", "fact_check_status": "passed"},
        },
    )

    assert "继续基于刚才的字节岗位改简历" in summary.summary
    assert summary.artifact_refs["job_snapshot_id"] == "js_001"
    assert summary.artifact_refs["match_assessment_id"] == "match_001"
    assert "assistant" not in summary.model_dump()


@pytest.mark.asyncio
async def test_conversation_memory_is_scoped_by_user(monkeypatch):
    saved: dict[str, ConversationMemorySnapshot] = {}

    class FakeStore:
        async def load_latest(self, user_id: str):
            return saved.get(user_id)

        async def save_turn(self, *, user_id: str, query: str, run_id: str, summary: str, artifact_refs: dict):
            saved[user_id] = ConversationMemorySnapshot(
                user_id=user_id,
                conversation_id=f"conv::{user_id}",
                summary=summary,
                artifact_refs=artifact_refs,
                updated_at="2026-05-06T00:00:00Z",
            )

    await save_memory_turn(
        store=FakeStore(),
        user_id="user_a",
        query="字节后端",
        state={"run_id": "run_a", "job_snapshot": {"job_snapshot_id": "js_a"}},
    )

    user_a = await load_memory_for_user(store=FakeStore(), user_id="user_a")
    user_b = await load_memory_for_user(store=FakeStore(), user_id="user_b")

    assert user_a is not None
    assert user_a.artifact_refs["job_snapshot_id"] == "js_a"
    assert user_b is None


@pytest.mark.asyncio
async def test_conversation_memory_ignores_blank_user_id():
    class ExplodingStore:
        async def load_latest(self, user_id: str):
            raise AssertionError("store should not be called")

    assert await load_memory_for_user(store=ExplodingStore(), user_id="") is None
