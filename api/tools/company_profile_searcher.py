from __future__ import annotations

from api.core.job_query import normalize_query_text
from api.tools.tavily_searcher import ToolSearchResult, search_tavily_queries


async def search_company_profile_sources(
    *,
    company: str,
    role: str,
    team_hint: str = "",
    domain_hint: str = "",
) -> ToolSearchResult:
    queries = [
        normalize_query_text(f"{company} {team_hint or role} 业务线 技术文化 团队特点 招聘"),
        normalize_query_text(f"{company} {domain_hint or role} 产品场景 组织特征 技术栈"),
    ]
    return await search_tavily_queries(
        tool_name="company_profile_searcher",
        search_queries=queries,
        raw_type="company_profile",
    )
