from __future__ import annotations

import pytest

from api.agents.search_agent import search_agent_node
from api.core.rag_store import RagChunk, RagSearchHit
from api.core.settings import get_settings
from api.tools import NormalizedSource, ToolSearchResult


def _source(*, raw_type: str, url: str) -> NormalizedSource:
    return NormalizedSource(
        query="字节 后端",
        url=url,
        title=f"{raw_type} source",
        snippet="字节跳动后端岗位要求熟悉 Redis。",
        published="2026-04-01",
        score="0.9",
        raw_type=raw_type,
    )


async def _tool_result(raw_type: str, url: str) -> ToolSearchResult:
    return ToolSearchResult(
        tool_name=f"{raw_type}_searcher",
        search_queries=[f"字节 后端 {raw_type}"],
        sources=[_source(raw_type=raw_type, url=url)],
    )


@pytest.mark.asyncio
async def test_search_agent_marks_rag_disabled_without_changing_retrieval(monkeypatch):
    monkeypatch.delenv("ENABLE_RAG", raising=False)
    get_settings.cache_clear()

    monkeypatch.setattr("api.agents.search_agent.search_company_profile_sources", lambda **_: _tool_result("company_profile", "https://example.com/company"))
    monkeypatch.setattr("api.agents.search_agent.search_jd_sources", lambda **_: _tool_result("jd", "https://example.com/jd"))
    monkeypatch.setattr("api.agents.search_agent.search_interview_sources", lambda **_: _tool_result("interview", "https://example.com/interview"))

    update = await search_agent_node(
        {
            "query": "字节后端实习",
            "intent": "general",
            "query_profile": {"company": "字节跳动", "role": "后端开发实习"},
            "insights": {},
        }
    )

    assert update["retrieval_diagnostics"]["rag_enabled"] is False
    assert update["retrieval_diagnostics"]["rag_hit_count"] == 0
    assert update["retrieval_diagnostics"]["rag_failures"] == []
    assert update["retrieval_diagnostics"]["rag_enabled"] is False


@pytest.mark.asyncio
async def test_search_agent_adds_pgvector_hits_as_job_side_evidence(monkeypatch):
    monkeypatch.setenv("ENABLE_RAG", "1")
    monkeypatch.setenv("RAG_TOP_K", "2")
    get_settings.cache_clear()

    monkeypatch.setattr("api.agents.search_agent.search_company_profile_sources", lambda **_: _tool_result("company_profile", "https://example.com/company"))
    monkeypatch.setattr("api.agents.search_agent.search_jd_sources", lambda **_: _tool_result("jd", "https://example.com/jd"))
    monkeypatch.setattr("api.agents.search_agent.search_interview_sources", lambda **_: _tool_result("interview", "https://example.com/interview"))

    async def fake_search_rag_sources(*, query, profile, top_k):
        assert top_k == 2
        return [
            RagSearchHit(
                chunk=RagChunk(
                    chunk_id="chunk_001",
                    document_id="doc_001",
                    source_type="jd",
                    title="历史 JD",
                    url="https://rag.example.com/jd",
                    text="岗位资料强调 Redis、MySQL 和消息队列。",
                    metadata={"company": profile["company"]},
                ),
                score=0.93,
            )
        ], []

    monkeypatch.setattr("api.agents.search_agent.search_rag_sources", fake_search_rag_sources)

    update = await search_agent_node(
        {
            "query": "字节后端实习",
            "intent": "general",
            "query_profile": {"company": "字节跳动", "role": "后端开发实习"},
            "insights": {},
        }
    )

    rag_items = [item for item in update["evidence_items"] if item["url"] == "https://rag.example.com/jd"]
    assert update["retrieval_diagnostics"]["rag_enabled"] is True
    assert update["retrieval_diagnostics"]["rag_hit_count"] == 1
    assert len(rag_items) >= 1, f"RAG item not in evidence_items: {[e['url'] for e in update['evidence_items']]}"
    assert rag_items[0]["source_class"] == "jd"
    assert rag_items[0]["url"] == "https://rag.example.com/jd"


@pytest.mark.asyncio
async def test_search_agent_deduplicates_rag_hits_by_url(monkeypatch):
    monkeypatch.setenv("ENABLE_RAG", "1")
    get_settings.cache_clear()

    monkeypatch.setattr("api.agents.search_agent.search_company_profile_sources", lambda **_: _tool_result("company_profile", "https://example.com/company"))
    monkeypatch.setattr("api.agents.search_agent.search_jd_sources", lambda **_: _tool_result("jd", "https://example.com/jd"))
    monkeypatch.setattr("api.agents.search_agent.search_interview_sources", lambda **_: _tool_result("interview", "https://example.com/interview"))

    async def fake_search_rag_sources(**_kwargs):
        return [
            RagSearchHit(
                chunk=RagChunk(
                    chunk_id="chunk_dup",
                    document_id="doc_dup",
                    source_type="jd",
                    title="重复 JD",
                    url="https://example.com/jd",
                    text="重复来源。",
                    metadata={},
                ),
                score=0.99,
            )
        ], []

    monkeypatch.setattr("api.agents.search_agent.search_rag_sources", fake_search_rag_sources)

    update = await search_agent_node(
        {
            "query": "字节后端实习",
            "intent": "general",
            "query_profile": {"company": "字节跳动", "role": "后端开发实习"},
            "insights": {},
        }
    )

    assert [item["url"] for item in update["evidence_items"]].count("https://example.com/jd") == 1
