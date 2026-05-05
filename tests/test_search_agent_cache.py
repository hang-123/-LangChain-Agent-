from __future__ import annotations

import copy
from pathlib import Path

import pytest

from api.agents.search_agent import search_agent_node
from api.core.cache import normalize_redis_url
from api.core.settings import get_settings
from api.tools import NormalizedSource, ToolSearchResult


def _source(*, query: str, url: str, title: str, snippet: str, raw_type: str) -> NormalizedSource:
    return NormalizedSource(
        query=query,
        url=url,
        title=title,
        snippet=snippet,
        published="2025-11-01",
        score="0.91",
        raw_type=raw_type,
    )


def test_normalize_redis_url_accepts_http_style_localhost():
    assert normalize_redis_url("http://localhost:6380/") == "redis://localhost:6380/0"


@pytest.mark.asyncio
async def test_search_agent_uses_sqlite_cache_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_CACHE", "1")
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "langgraph_cache.sqlite"))
    get_settings.cache_clear()

    calls = {"company": 0, "jd": 0, "interview": 0}

    async def fake_company_profile_sources(**_kwargs):
        calls["company"] += 1
        return ToolSearchResult(
            tool_name="company_profile_searcher",
            search_queries=["字节跳动 后端 公司画像"],
            sources=[
                _source(
                    query="字节跳动 后端 公司画像",
                    url="https://example.com/company",
                    title="字节跳动后端团队画像",
                    snippet="字节跳动后端团队关注工程质量与高并发能力。",
                    raw_type="company_profile",
                )
            ],
        )

    async def fake_jd_sources(**_kwargs):
        calls["jd"] += 1
        return ToolSearchResult(
            tool_name="jd_searcher",
            search_queries=["字节跳动 后端 JD"],
            sources=[
                _source(
                    query="字节跳动 后端 JD",
                    url="https://example.com/jd",
                    title="字节跳动后端开发 JD",
                    snippet="岗位要求熟悉 Python、Go 与分布式系统。",
                    raw_type="jd",
                )
            ],
        )

    async def fake_interview_sources(**_kwargs):
        calls["interview"] += 1
        return ToolSearchResult(
            tool_name="interview_searcher",
            search_queries=["字节跳动 后端 面经"],
            sources=[
                _source(
                    query="字节跳动 后端 面经",
                    url="https://example.com/interview",
                    title="字节跳动后端面经",
                    snippet="面试追问项目抽象、缓存一致性与高并发场景。",
                    raw_type="interview",
                )
            ],
        )

    monkeypatch.setattr("api.agents.search_agent.search_company_profile_sources", fake_company_profile_sources)
    monkeypatch.setattr("api.agents.search_agent.search_jd_sources", fake_jd_sources)
    monkeypatch.setattr("api.agents.search_agent.search_interview_sources", fake_interview_sources)

    state = {
        "query": "字节跳动后端开发实习生面试准备",
        "intent": "general",
        "query_profile": {
            "company": "字节跳动",
            "role": "后端开发实习生",
            "team_hint": "",
            "domain_hint": "",
            "job_level": "实习",
            "priority_topics": ["高并发"],
        },
        "insights": {},
    }

    first = await search_agent_node(state)
    second = await search_agent_node(state)

    assert first["retrieval_diagnostics"]["cached"] is False
    assert second["retrieval_diagnostics"]["cached"] is True
    assert second["retrieval_diagnostics"]["cache_backend"] == "sqlite"
    assert calls == {"company": 1, "jd": 1, "interview": 1}
    assert Path(str(tmp_path / "langgraph_cache.sqlite")).exists()

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_search_agent_prefers_redis_cache_when_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_CACHE", "1")
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "langgraph_cache.sqlite"))
    monkeypatch.setenv("REDIS_URL", "http://localhost:6380/")
    get_settings.cache_clear()

    calls = {"company": 0, "jd": 0, "interview": 0}
    store: dict[tuple[str, str], dict[str, object]] = {}

    class FakeRedisCache:
        def get(self, namespace: str, key: str):
            payload = store.get((namespace, key))
            return copy.deepcopy(payload) if payload is not None else None

        def set(self, namespace: str, key: str, payload: dict[str, object], *, ttl_seconds: int):
            assert ttl_seconds > 0
            store[(namespace, key)] = copy.deepcopy(payload)

    async def fake_company_profile_sources(**_kwargs):
        calls["company"] += 1
        return ToolSearchResult(
            tool_name="company_profile_searcher",
            search_queries=["字节跳动 后端 公司画像"],
            sources=[
                _source(
                    query="字节跳动 后端 公司画像",
                    url="https://example.com/company",
                    title="字节跳动后端团队画像",
                    snippet="字节跳动后端团队关注工程质量与高并发能力。",
                    raw_type="company_profile",
                )
            ],
        )

    async def fake_jd_sources(**_kwargs):
        calls["jd"] += 1
        return ToolSearchResult(
            tool_name="jd_searcher",
            search_queries=["字节跳动 后端 JD"],
            sources=[
                _source(
                    query="字节跳动 后端 JD",
                    url="https://example.com/jd",
                    title="字节跳动后端开发 JD",
                    snippet="岗位要求熟悉 Python、Go 与分布式系统。",
                    raw_type="jd",
                )
            ],
        )

    async def fake_interview_sources(**_kwargs):
        calls["interview"] += 1
        return ToolSearchResult(
            tool_name="interview_searcher",
            search_queries=["字节跳动 后端 面经"],
            sources=[
                _source(
                    query="字节跳动 后端 面经",
                    url="https://example.com/interview",
                    title="字节跳动后端面经",
                    snippet="面试追问项目抽象、缓存一致性与高并发场景。",
                    raw_type="interview",
                )
            ],
        )

    monkeypatch.setattr("api.agents.search_agent.get_redis_json_cache", lambda _url: FakeRedisCache())
    monkeypatch.setattr("api.agents.search_agent.search_company_profile_sources", fake_company_profile_sources)
    monkeypatch.setattr("api.agents.search_agent.search_jd_sources", fake_jd_sources)
    monkeypatch.setattr("api.agents.search_agent.search_interview_sources", fake_interview_sources)

    state = {
        "query": "字节跳动后端开发实习生面试准备",
        "intent": "general",
        "query_profile": {
            "company": "字节跳动",
            "role": "后端开发实习生",
            "team_hint": "",
            "domain_hint": "",
            "job_level": "实习",
            "priority_topics": ["高并发"],
        },
        "insights": {},
    }

    first = await search_agent_node(state)
    second = await search_agent_node(state)

    assert first["retrieval_diagnostics"]["cached"] is False
    assert second["retrieval_diagnostics"]["cached"] is True
    assert second["retrieval_diagnostics"]["cache_backend"] == "redis"
    assert calls == {"company": 1, "jd": 1, "interview": 1}

    get_settings.cache_clear()
