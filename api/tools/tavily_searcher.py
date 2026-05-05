from __future__ import annotations

import re
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from api.core.settings import get_settings


class NormalizedSource(BaseModel):
    query: str
    url: str
    title: str
    snippet: str
    published: str
    score: str
    raw_type: str


class ToolSearchResult(BaseModel):
    tool_name: str
    search_queries: list[str] = Field(default_factory=list)
    sources: list[NormalizedSource] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


def _normalize_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:520]


async def _search_once(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    query: str,
    max_results: int,
    depth: Literal["advanced", "basic"],
) -> dict:
    response = await client.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "topic": "general",
            "search_depth": depth,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": True,
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("unexpected Tavily payload")
    return payload


async def search_tavily_queries(
    *,
    tool_name: str,
    search_queries: list[str],
    raw_type: str,
    max_results: int | None = None,
) -> ToolSearchResult:
    settings = get_settings()
    tavily_api_key = settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else ""
    limit = max_results or settings.tavily_max_results

    if not tavily_api_key:
        return ToolSearchResult(
            tool_name=tool_name,
            search_queries=search_queries,
            failures=["missing:TAVILY_API_KEY"],
        )

    sources: list[NormalizedSource] = []
    failures: list[str] = []
    seen_urls: set[str] = set()

    timeout = httpx.Timeout(timeout=20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for search_query in search_queries:
            payload: dict | None = None
            errors: list[str] = []

            for depth in ("advanced", "basic"):
                try:
                    payload = await _search_once(
                        client,
                        api_key=tavily_api_key,
                        query=search_query,
                        max_results=limit,
                        depth=depth,
                    )
                    break
                except Exception as exc:
                    errors.append(f"{depth}:{exc}")

            if payload is None:
                failures.extend(f"{tool_name}:{search_query}:{error}" for error in errors[:2])
                continue

            for item in payload.get("results") or []:
                url = str(item.get("url") or "").strip()
                snippet = _normalize_snippet(
                    str(item.get("content") or item.get("raw_content") or item.get("description") or "")
                )
                if not url or not snippet or url in seen_urls:
                    continue

                seen_urls.add(url)
                sources.append(
                    NormalizedSource(
                        query=search_query,
                        url=url,
                        title=str(item.get("title") or "").strip() or "无标题",
                        snippet=snippet,
                        published=str(item.get("published_date") or item.get("published_at") or "未知").strip(),
                        score=str(item.get("score") or "").strip(),
                        raw_type=raw_type,
                    )
                )

    return ToolSearchResult(
        tool_name=tool_name,
        search_queries=search_queries,
        sources=sources,
        failures=failures[:8],
    )
