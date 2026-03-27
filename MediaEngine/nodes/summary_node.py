from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser

from ..config import MediaEngineConfig
from ..llms import build_llm
from ..prompts import MEDIA_SUMMARY_PROMPT, MediaSummaryOutput
from ..state import MediaState
from .base import MediaNode


class MediaSummaryNode(MediaNode):
    name = "media_summary"

    def __init__(self, config: MediaEngineConfig):
        self.config = config
        self.llm = build_llm(config)
        self.parser = PydanticOutputParser(pydantic_object=MediaSummaryOutput)
        self.prompt = MEDIA_SUMMARY_PROMPT.partial(
            format_instructions=self.parser.get_format_instructions()
        )

    async def arun(self, state: MediaState) -> MediaState:
        evidence_lines = []
        for article in state.articles:
            evidence_lines.append(f"[Article] {article.title}\n{article.description}\n{article.url}")
        for visual in state.visuals:
            evidence_lines.append(f"[Visual] {visual.title}\n{visual.description}\n{visual.url}")
        evidence = "\n\n".join(evidence_lines) or "暂无结果"
        state.record_event(self.name, "summarizing media narratives")
        output: MediaSummaryOutput = await (self.prompt | self.llm | self.parser).ainvoke(
            {"query": state.query, "evidence": evidence}
        )
        state.highlights = output.highlights
        state.risks = output.emerging_risks
        state.sentiment = output.sentiment_overview
        # Use textual references for visuals
        if output.visual_references:
            state.visuals = state.visuals[: len(output.visual_references)]
        state.record_event(self.name, "summary structured")
        return state

