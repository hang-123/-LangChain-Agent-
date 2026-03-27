from __future__ import annotations

from ..config import QueryEngineConfig
from ..llms import LLMOrchestrator
from ..state import AgentState
from .base import BaseNode


class ReportFormattingNode(BaseNode):
    name = "report_formatting"

    def __init__(self, orchestrator: LLMOrchestrator, config: QueryEngineConfig):
        self.orchestrator = orchestrator
        self.config = config

    async def arun(self, state: AgentState) -> AgentState:
        report_title = state.report_title or state.query
        state.report_markdown = await self.orchestrator.format_report(report_title, state.paragraphs)
        state.record_event(self.name, "report assembled")
        return state

