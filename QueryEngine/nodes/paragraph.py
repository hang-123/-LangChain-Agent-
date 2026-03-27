from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..config import QueryEngineConfig
from ..llms import LLMOrchestrator
from ..state import AgentState, ParagraphPlan, SearchHistory, SearchResult
from ..tools import InternalVectorToolset, TavilyResponse, TavilyToolset
from .base import BaseNode


class ParagraphResearchNode(BaseNode):
    name = "paragraph_research"

    def __init__(
        self,
        orchestrator: LLMOrchestrator,
        tavily_tools: TavilyToolset,
        internal_tools: Optional[InternalVectorToolset],
        config: QueryEngineConfig,
    ):
        self.orchestrator = orchestrator
        self.tavily_tools = tavily_tools
        self.internal_tools = internal_tools
        self.config = config

    async def arun(self, state: AgentState) -> AgentState:
        for paragraph in state.paragraphs:
            await self._process_paragraph(state, paragraph)
        state.record_event(self.name, "completed paragraph research")
        return state

    async def _process_paragraph(self, state: AgentState, paragraph: ParagraphPlan) -> None:
        for iteration in range(self.config.max_reflections + 1):
            plan = await self.orchestrator.plan_search(paragraph, state.query)
            response = self._execute_tool(plan.tool, plan.search_query, plan.start_date, plan.end_date)
            state.record_event(
                self.name,
                f"{paragraph.title}: tool={plan.tool} query={plan.search_query} results={len(response.results)}",
            )
            paragraph.add_search(SearchHistory(query=plan.search_query, tool_used=plan.tool, results=response.results))

            paragraph.latest_summary = await self.orchestrator.summarize(paragraph, state.query, response.results)
            if iteration >= self.config.max_reflections:
                break

            reflection = await self.orchestrator.reflect(paragraph)
            paragraph.reflections += 1
            if not reflection.needs_more_research:
                break

    def _execute_tool(
        self,
        tool_name: str,
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TavilyResponse:
        name = (tool_name or "").strip().lower()
        if name == "internal_vector_search":
            if not self.internal_tools:
                return self.tavily_tools.basic_search(query, max_results=self.config.max_search_results)
            return self.internal_tools.search(query)
        if name == "internal_kg_search":
            # 使用 InsightEngine 的知识图谱查询，返回结构化关系，再封装成 SearchResult
            try:
                from InsightEngine.tools.graph_search import search_kg_for_topic  # type: ignore[import]
            except Exception:
                # 如果未配置 KG，则回退到基础新闻搜索
                return self.tavily_tools.basic_search(query, max_results=self.config.max_search_results)

            try:
                kg_relations = search_kg_for_topic(query, limit=self.config.max_search_results)
            except Exception:
                return self.tavily_tools.basic_search(query, max_results=self.config.max_search_results)

            results: list[SearchResult] = []
            for rel in kg_relations:
                arrow = "->" if getattr(rel, "direction", "out") == "out" else "<-"
                title = f"{rel.head} -[{rel.relation}]{arrow} {rel.tail}"
                content = (
                    f"{title}\n"
                    f"source={rel.source or '-'}, "
                    f"confidence={rel.confidence if rel.confidence is not None else '-'}"
                )
                results.append(
                    SearchResult(
                        title=title,
                        url="",
                        content=content,
                    )
                )
            return TavilyResponse(query=query, tool_name="internal_kg_search", results=results)

        if name == "deep_search_news":
            return self.tavily_tools.deep_search(query, max_results=self.config.max_search_results)
        if name == "search_news_last_24_hours":
            return self.tavily_tools.last_24h(query, max_results=self.config.max_search_results)
        if name == "search_news_last_week":
            return self.tavily_tools.last_week(query, max_results=self.config.max_search_results)
        if name == "search_images_for_news":
            return self.tavily_tools.search_images(query, max_results=self.config.max_search_results)
        if name == "search_news_by_date":
            start, end = self._resolve_dates(start_date, end_date)
            return self.tavily_tools.search_by_date(
                query,
                start_date=start,
                end_date=end,
                max_results=self.config.max_search_results,
            )

        return self.tavily_tools.basic_search(query, max_results=self.config.max_search_results)

    @staticmethod
    def _resolve_dates(start_date: Optional[str], end_date: Optional[str]) -> tuple[str, str]:
        if start_date and end_date:
            return start_date, end_date
        today = datetime.utcnow().date()
        default_end = end_date or today.isoformat()
        default_start = start_date or (today - timedelta(days=7)).isoformat()
        return default_start, default_end
