"""
Public interface for running the LangChain-based Query Agent.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import QueryEngineConfig
from .llms import LLMOrchestrator
from .nodes import ParagraphResearchNode, ReportFormattingNode, ReportStructureNode
from .state import AgentState
from .tools import InternalVectorToolset, TavilyToolset
from utils.logger import log_agent_run


@dataclass
class QueryAgentResult:
    report_markdown: str
    state: AgentState
    report_file: Optional[Path]
    state_file: Optional[Path]


class QueryAgent:
    def __init__(self, config: Optional[QueryEngineConfig] = None):
        self.config = config or QueryEngineConfig.from_env()
        self.config.validate()
        self.llm = LLMOrchestrator(self.config)
        self.tools = TavilyToolset(api_key=self.config.tavily_api_key)  # type: ignore[arg-type]
        # Internal vector search (optional). If PG retriever not available, set to None.
        try:
            self.internal_tools: Optional[InternalVectorToolset] = InternalVectorToolset()
        except Exception:
            self.internal_tools = None
        self.nodes = [
            ReportStructureNode(self.llm, self.config),
            ParagraphResearchNode(self.llm, self.tools, self.internal_tools, self.config),
            ReportFormattingNode(self.llm, self.config),
        ]

    def run(self, query: str, save_report: bool = True) -> QueryAgentResult:
        return asyncio.run(self._run_pipeline(query, save_report))

    async def _run_pipeline(self, query: str, save_report: bool) -> QueryAgentResult:
        state = AgentState(query=query)

        for node in self.nodes:
            state = await node.arun(state)

        state.mark_completed()
        log_agent_run(
            "query",
            query,
            summary=(state.report_markdown[:200] + "...") if state.report_markdown else "No report generated.",
            events=state.events,
        )

        report_path = state_path = None
        if save_report:
            report_path = self._save_report(state.report_markdown, state)
            if self.config.save_intermediate_state:
                state_path = self._save_state(state)

        return QueryAgentResult(
            report_markdown=state.report_markdown,
            state=state,
            report_file=report_path,
            state_file=state_path,
        )

    def _save_report(self, markdown: str, state: AgentState) -> Path:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        safe_query = "".join(c for c in state.query if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        filename = f"deep_search_report_{safe_query}_{state.created_at.replace(':', '').replace('-', '')}.md"
        path = self.config.output_dir / filename
        path.write_text(markdown, encoding="utf-8")
        return path

    def _save_state(self, state: AgentState) -> Path:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        safe_query = "".join(c for c in state.query if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        filename = f"state_{safe_query}_{state.created_at.replace(':', '').replace('-', '')}.json"
        path = self.config.output_dir / filename
        state.save(path)
        return path
