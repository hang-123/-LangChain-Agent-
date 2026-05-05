from __future__ import annotations

from api.core.job_query import normalize_query_text
from api.tools.tavily_searcher import ToolSearchResult, search_tavily_queries


async def search_jd_sources(
    *,
    company: str,
    role: str,
    team_hint: str = "",
    domain_hint: str = "",
    job_level: str = "",
) -> ToolSearchResult:
    role_phrase = team_hint or role
    search_queries = [
        normalize_query_text(f"{company} {role_phrase} {job_level} 最新 招聘 JD 任职要求 技术栈"),
        normalize_query_text(f"{company} {role_phrase} {domain_hint} 岗位职责 任职资格 技能要求"),
    ]
    return await search_tavily_queries(
        tool_name="jd_searcher",
        search_queries=search_queries,
        raw_type="jd",
    )
