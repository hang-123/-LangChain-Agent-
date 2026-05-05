from __future__ import annotations

from api.core.job_query import normalize_query_text
from api.tools.tavily_searcher import ToolSearchResult, search_tavily_queries


async def search_interview_sources(
    *,
    company: str,
    role: str,
    team_hint: str = "",
    domain_hint: str = "",
    priority_topics: list[str] | None = None,
) -> ToolSearchResult:
    focus = " ".join((priority_topics or [])[:2]).strip()
    role_phrase = team_hint or role
    search_queries = [
        normalize_query_text(f"{company} {role_phrase} 面经 面试题 面试流程"),
        normalize_query_text(f"{company} {role_phrase} {domain_hint} 高频追问 {focus or '系统设计'}"),
    ]
    return await search_tavily_queries(
        tool_name="interview_searcher",
        search_queries=search_queries,
        raw_type="interview",
    )
