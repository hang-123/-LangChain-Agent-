"""Tests for the new memory system (api/core/memory/)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from api.core.memory.models import (
    ConversationSessionStatus,
    LongTermMemory,
    MemoryHit,
    MemoryType,
    SourceType,
    TurnSummary,
    build_memory_tags,
    extract_keywords,
)
from api.core.memory.stm_store import SqliteConversationMemoryStore
from api.core.memory.ltm_store import SqliteLongTermMemoryStore
from api.core.memory.retrieval import (
    MemoryContext,
    reciprocal_rank_fusion,
    rerank_by_recency_importance,
    retrieve_memories,
)
from api.core.memory.consolidation import (
    consolidate_session,
    run_periodic_maintenance,
    score_importance,
    classify_memory_type,
)
from api.core.memory.consolidation import TurnRecord as ConsolidationTurnRecord


# ── Models ──


class TestModels:
    def test_turn_summary_roundtrip(self):
        ts = TurnSummary(
            query="test query",
            company="Databricks",
            role="Senior SWE",
            archetype="AI Platform / LLMOps",
            overall_score=4.2,
            recommendation="strong_recommend",
            key_findings=["Strong ML background", "Gap: Kubernetes"],
            tags=["company:databricks", "role:senior_swe"],
        )
        data = ts.model_dump()
        ts2 = TurnSummary.model_validate(data)
        assert ts2.company == "Databricks"
        assert ts2.overall_score == 4.2

    def test_build_memory_tags(self):
        tags = build_memory_tags(
            company="Databricks",
            role="Senior SWE",
            archetype="AI Platform / LLMOps",
            score=4.2,
            recommendation="strong_recommend",
        )
        assert "company:databricks" in tags
        assert "role:senior swe" in tags
        assert "archetype:ai platform / llmops" in tags
        assert "score:high" in tags
        assert "rec:strong_recommend" in tags

    def test_build_memory_tags_low_score(self):
        tags = build_memory_tags(score=2.5)
        assert "score:low" in tags

    def test_build_memory_tags_medium_score(self):
        tags = build_memory_tags(score=3.5)
        assert "score:medium" in tags

    def test_extract_keywords(self):
        kws = extract_keywords("Senior Backend Engineer at Databricks")
        assert "senior" in kws
        assert "backend" in kws
        assert "engineer" in kws
        assert "databricks" in kws
        # stopwords filtered
        assert "at" not in kws
        assert "the" not in kws

    def test_long_term_memory_model(self):
        mem = LongTermMemory(
            memory_id="mem-001",
            user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="Evaluated Databricks Senior SWE, score 4.2",
            importance=0.8,
        )
        assert mem.memory_type == MemoryType.EPISODIC
        assert mem.importance == 0.8


# ── STM Store ──


class TestSTMStore:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_stm.sqlite"
            store = SqliteConversationMemoryStore(str(db_path))
            yield store

    @pytest.mark.asyncio
    async def test_ensure_session_creates(self, store):
        sid = await store.ensure_session("user_001")
        assert sid.startswith("sess-")

    @pytest.mark.asyncio
    async def test_ensure_session_reuses_active(self, store):
        sid1 = await store.ensure_session("user_001")
        sid2 = await store.ensure_session("user_001")
        assert sid1 == sid2

    @pytest.mark.asyncio
    async def test_end_session(self, store):
        sid = await store.ensure_session("user_001")
        await store.end_session(sid)
        # new active session should be created after ending
        sid2 = await store.ensure_session("user_001")
        assert sid2 != sid

    @pytest.mark.asyncio
    async def test_save_and_load_turns(self, store):
        sid = await store.ensure_session("user_001")
        ts = TurnSummary(
            query="Evaluate Databricks Senior SWE",
            company="Databricks",
            role="Senior SWE",
            overall_score=4.2,
        )
        tid = await store.save_turn(
            user_id="user_001",
            session_id=sid,
            run_id="run_001",
            query="test query",
            summary=ts,
        )
        assert tid > 0

        turns = await store.load_turns("user_001")
        assert len(turns) == 1
        assert turns[0].summary.company == "Databricks"

    @pytest.mark.asyncio
    async def test_load_latest_summary(self, store):
        sid = await store.ensure_session("user_001")
        ts = TurnSummary(company="Cohere", overall_score=3.8)
        await store.save_turn(
            user_id="user_001", session_id=sid, run_id="run_001",
            query="q1", summary=ts,
        )
        summary = await store.load_latest_summary("user_001")
        assert summary is not None
        assert summary.company == "Cohere"

    @pytest.mark.asyncio
    async def test_load_latest_summary_empty(self, store):
        summary = await store.load_latest_summary("nonexistent")
        assert summary is None

    @pytest.mark.asyncio
    async def test_load_session_metadata(self, store):
        sid = await store.ensure_session("user_001")
        ts = TurnSummary(company="Meta")
        await store.save_turn(
            user_id="user_001", session_id=sid, run_id="run_001",
            query="q", summary=ts,
        )
        session = await store.load_session(sid)
        assert session is not None
        assert session.turn_count == 1
        assert session.status == ConversationSessionStatus.ACTIVE


# ── LTM Store ──


class TestLTMStore:
    @pytest.fixture
    def ltm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_ltm.sqlite"
            store = SqliteLongTermMemoryStore(str(db_path))
            yield store

    @pytest.mark.asyncio
    async def test_save_and_get(self, ltm):
        mem = LongTermMemory(
            memory_id="mem-001",
            user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="Evaluated Databricks Senior SWE, score 4.2",
            importance=0.8,
        )
        mid = await ltm.save(mem)
        assert mid == "mem-001"

        loaded = await ltm.get("mem-001")
        assert loaded is not None
        assert loaded.content == mem.content

    @pytest.mark.asyncio
    async def test_search_by_user(self, ltm):
        await ltm.save(LongTermMemory(
            memory_id="mem-001", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="Evaluated Databricks Senior SWE, score 4.2",
            importance=0.8,
        ))
        await ltm.save(LongTermMemory(
            memory_id="mem-002", user_id="user_001",
            memory_type=MemoryType.SEMANTIC,
            source_type=SourceType.USER_PREFERENCE,
            content="User prefers large companies",
            importance=0.5,
        ))
        # Different user — should not appear
        await ltm.save(LongTermMemory(
            memory_id="mem-003", user_id="user_002",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="Other user memory",
        ))

        results = await ltm.search_by_user("user_001")
        assert len(results) == 2

        # Filter by memory_type
        results = await ltm.search_by_user("user_001", memory_type=MemoryType.SEMANTIC)
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.SEMANTIC

    @pytest.mark.asyncio
    async def test_update_access(self, ltm):
        await ltm.save(LongTermMemory(
            memory_id="mem-001", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="test",
        ))
        await ltm.update_access("mem-001")
        mem = await ltm.get("mem-001")
        assert mem is not None
        assert mem.access_count == 1
        assert mem.last_accessed_at

    @pytest.mark.asyncio
    async def test_delete(self, ltm):
        await ltm.save(LongTermMemory(
            memory_id="mem-001", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="test",
        ))
        result = await ltm.delete("mem-001")
        assert result is True
        mem = await ltm.get("mem-001")
        assert mem is not None
        assert mem.importance == 0.0

    @pytest.mark.asyncio
    async def test_apply_decay(self, ltm):
        await ltm.save(LongTermMemory(
            memory_id="mem-001", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="never accessed",
            importance=0.8,
            access_count=0,
        ))
        await ltm.save(LongTermMemory(
            memory_id="mem-002", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="frequently accessed",
            importance=0.5,
            access_count=5,
        ))
        decayed = await ltm.apply_decay("user_001")

        # mem-001 should be decayed (access_count=0)
        assert decayed >= 1
        mem1 = await ltm.get("mem-001")
        assert mem1 is not None
        assert mem1.importance < 0.8

    @pytest.mark.asyncio
    async def test_expire(self, ltm):
        await ltm.save(LongTermMemory(
            memory_id="mem-001", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="low importance, expired",
            importance=0.05,
            expires_at="2020-01-01T00:00:00Z",
        ))
        count = await ltm.expire("user_001")
        assert count >= 1
        mem = await ltm.get("mem-001")
        assert mem is None

    @pytest.mark.asyncio
    async def test_count_by_user(self, ltm):
        await ltm.save(LongTermMemory(
            memory_id="mem-001", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="test 1",
        ))
        await ltm.save(LongTermMemory(
            memory_id="mem-002", user_id="user_001",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="test 2",
        ))
        count = await ltm.count_by_user("user_001")
        assert count == 2


# ── Retrieval ──


class TestRetrieval:
    def test_reciprocal_rank_fusion(self):
        mem1 = LongTermMemory(
            memory_id="mem-001", user_id="u1",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="A",
        )
        mem2 = LongTermMemory(
            memory_id="mem-002", user_id="u1",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="B",
        )
        list_a = [MemoryHit(memory=mem1, score=0.9, retrieval_method="vector")]
        list_b = [MemoryHit(memory=mem1, score=0.5, retrieval_method="keyword"),
                  MemoryHit(memory=mem2, score=0.8, retrieval_method="keyword")]

        merged = reciprocal_rank_fusion(list_a, list_b)
        assert len(merged) == 2
        # mem1 appears in both lists → should rank higher
        assert merged[0].memory.memory_id == "mem-001"
        assert merged[0].retrieval_method == "hybrid"

    def test_rerank_by_recency_importance(self):
        old_mem = LongTermMemory(
            memory_id="mem-old", user_id="u1",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="old",
            importance=0.5,
            created_at="2020-01-01T00:00:00Z",
        )
        new_mem = LongTermMemory(
            memory_id="mem-new", user_id="u1",
            memory_type=MemoryType.EPISODIC,
            source_type=SourceType.EVALUATION_REPORT,
            content="new",
            importance=0.8,
            created_at="2026-05-01T00:00:00Z",
        )
        hits = [
            MemoryHit(memory=old_mem, score=0.7),
            MemoryHit(memory=new_mem, score=0.7),
        ]
        reranked = rerank_by_recency_importance(hits)
        assert reranked[0].memory.memory_id == "mem-new"

    @pytest.mark.asyncio
    async def test_retrieve_memories_empty_without_store(self):
        result = await retrieve_memories(
            ltm_store=None,
            stm_store=None,
            query="test",
            query_profile={},
            user_id="user_001",
        )
        assert isinstance(result, MemoryContext)
        assert result.hit_count == 0
        assert result.formatted_text == ""

    @pytest.mark.asyncio
    async def test_retrieve_memories_with_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ltm = SqliteLongTermMemoryStore(str(Path(tmpdir) / "ltm.sqlite"))
            await ltm.save(LongTermMemory(
                memory_id="mem-001", user_id="user_001",
                memory_type=MemoryType.EPISODIC,
                source_type=SourceType.EVALUATION_REPORT,
                content="Evaluated Databricks Senior Backend Engineer, score 4.2. Key: strong distributed systems background. Gap: no Go experience.",
                importance=0.8,
            ))

            result = await retrieve_memories(
                ltm_store=ltm,
                stm_store=None,
                query="Evaluate Databricks Senior SWE role",
                query_profile={"company": "Databricks", "role": "Senior SWE"},
                user_id="user_001",
                top_k=3,
            )
            assert result.hit_count > 0
            assert "Databricks" in result.formatted_text


# ── Consolidation ──


class TestConsolidation:
    def test_score_importance_high(self):
        turn = _make_turn(score=4.5, findings=["a", "b", "c"])
        assert score_importance(turn) >= 0.8

    def test_score_importance_low(self):
        turn = _make_turn(score=2.0, findings=[])
        assert score_importance(turn) <= 0.35

    def test_classify_memory_type(self):
        turn = _make_turn(score=4.0, recommendation="strong_recommend")
        assert classify_memory_type(turn) == MemoryType.EPISODIC

        turn2 = _make_turn(archetype="AI Platform / LLMOps")
        assert classify_memory_type(turn2) == MemoryType.SEMANTIC

    @pytest.mark.asyncio
    async def test_consolidate_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stm = SqliteConversationMemoryStore(str(Path(tmpdir) / "stm.sqlite"))
            ltm = SqliteLongTermMemoryStore(str(Path(tmpdir) / "ltm.sqlite"))

            sid = await stm.ensure_session("user_001")
            ts = TurnSummary(
                query="Evaluate Databricks",
                company="Databricks",
                role="Senior SWE",
                overall_score=4.2,
                recommendation="strong_recommend",
                archetype="AI Platform / LLMOps",
                key_findings=["Strong ML", "Distributed systems"],
            )
            await stm.save_turn(
                user_id="user_001", session_id=sid,
                run_id="run_001", query="test", summary=ts,
            )

            created = await consolidate_session(
                stm_store=stm,
                ltm_store=ltm,
                user_id="user_001",
                session_id=sid,
            )
            assert created >= 1

            # Verify LTM has the memory
            count = await ltm.count_by_user("user_001")
            assert count >= 1

            # Verify session was ended
            session = await stm.load_session(sid)
            assert session is not None
            assert session.status == ConversationSessionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_periodic_maintenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ltm = SqliteLongTermMemoryStore(str(Path(tmpdir) / "ltm.sqlite"))
            await ltm.save(LongTermMemory(
                memory_id="mem-001", user_id="user_001",
                memory_type=MemoryType.EPISODIC,
                source_type=SourceType.EVALUATION_REPORT,
                content="never accessed",
                importance=0.3,
                access_count=0,
            ))
            await ltm.save(LongTermMemory(
                memory_id="mem-002", user_id="user_001",
                memory_type=MemoryType.EPISODIC,
                source_type=SourceType.EVALUATION_REPORT,
                content="dead memory",
                importance=0.05,
                expires_at="2020-01-01T00:00:00Z",
            ))
            result = await run_periodic_maintenance(ltm_store=ltm, user_id="user_001")
            assert result["decayed"] >= 1
            assert result["expired"] >= 1


# ── Helpers ──


def _make_turn(
    score: float | None = None,
    findings: list[str] | None = None,
    recommendation: str | None = None,
    archetype: str | None = None,
) -> ConsolidationTurnRecord:
    return ConsolidationTurnRecord(
        user_id="user_001",
        session_id="sess-test",
        run_id="run_test",
        query="test query",
        summary=TurnSummary(
            query="test query",
            company="TestCo",
            role="Test Role",
            overall_score=score,
            recommendation=recommendation,
            archetype=archetype,
            key_findings=findings or [],
        ),
    )
