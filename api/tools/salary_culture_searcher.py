from __future__ import annotations

from api.core.job_query import normalize_query_text
from api.tools.tavily_searcher import ToolSearchResult, search_tavily_queries


async def search_salary_culture_sources(
    *,
    company: str,
    role: str,
    team_hint: str = "",
    job_level: str = "",
) -> ToolSearchResult:
    role_phrase = team_hint or role
    search_queries = [
        normalize_query_text(f"{company} {role_phrase} {job_level} 薪资 区间 职级 待遇"),
        normalize_query_text(f"{company} {role_phrase} 团队文化 WLB 口碑 工作节奏"),
    ]
    return await search_tavily_queries(
        tool_name="salary_culture_searcher",
        search_queries=search_queries,
        raw_type="salary_culture",
    )
