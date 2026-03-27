from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser

from ..config import ReportEngineConfig
from ..llms import build_llm
from ..prompts import REPORT_PLAN_PROMPT, ReportPlanOutput
from ..state import ReportSection, ReportState
from .base import ReportNode


class PlanNode(ReportNode):
    name = "report_plan"

    def __init__(self, config: ReportEngineConfig):
        self.llm = build_llm(config)
        self.parser = PydanticOutputParser(pydantic_object=ReportPlanOutput)
        self.prompt = REPORT_PLAN_PROMPT.partial(
            format_instructions=self.parser.get_format_instructions()
        )
        self.max_sections = config.max_sections

    async def arun(self, state: ReportState) -> ReportState:
        plan: ReportPlanOutput = await (self.prompt | self.llm | self.parser).ainvoke(
            {"query": state.query, "sources": state.compiled_sources}
        )
        state.executive_summary = plan.executive_summary
        state.sections = []
        for section in plan.sections[: self.max_sections]:
            title = section.get("title") or "未命名章节"
            summary = section.get("summary") or ""
            state.sections.append(ReportSection(title=title, summary=summary))
        return state

