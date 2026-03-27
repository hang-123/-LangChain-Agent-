from __future__ import annotations

from ..config import QueryEngineConfig
from ..llms import LLMOrchestrator
from ..state import AgentState, ParagraphPlan
from .base import BaseNode


class ReportStructureNode(BaseNode):
    name = "report_structure"

    def __init__(self, orchestrator: LLMOrchestrator, config: QueryEngineConfig):
        self.orchestrator = orchestrator
        self.config = config

    async def arun(self, state: AgentState) -> AgentState:
        state.record_event(self.name, "generating outline")
        structure = await self.orchestrator.generate_structure(state.query)
        state.report_title = structure.report_title or state.query
        state.paragraphs = []
        for blueprint in structure.paragraphs[: self.config.max_paragraphs]:
            state.add_paragraph(ParagraphPlan(title=blueprint.title, expectation=blueprint.expectation))
        state.record_event(self.name, f"created {len(state.paragraphs)} sections")
        return state

