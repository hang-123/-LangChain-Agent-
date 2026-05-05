from __future__ import annotations

from api.core.job_query import normalize_query_text
from api.tools.tavily_searcher import ToolSearchResult, search_tavily_queries


async def search_tech_stack_sources(
    *,
    company: str,
    role: str,
    team_hint: str = "",
    domain_hint: str = "",
    priority_topics: list[str] | None = None,
) -> ToolSearchResult:
    focus = " ".join((priority_topics or [])[:3]).strip()
    role_phrase = team_hint or role
    search_queries = [
        normalize_query_text(f"{company} {role_phrase} {domain_hint} 技术栈 系统设计 工程关键词"),
        normalize_query_text(f"{company} {role_phrase} {focus or '算法 编码题 数据结构 性能优化'}"),
    ]
    return await search_tavily_queries(
        tool_name="tech_stack_searcher",
        search_queries=search_queries,
        raw_type="tech_stack",
    )
