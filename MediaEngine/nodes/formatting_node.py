from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser

from ..config import MediaEngineConfig
from ..llms import build_llm
from ..prompts import MEDIA_FORMAT_PROMPT
from ..state import MediaState
from .base import MediaNode


class MediaFormattingNode(MediaNode):
    name = "media_formatting"

    def __init__(self, config: MediaEngineConfig):
        self.config = config
        self.llm = build_llm(config)
        self.prompt = MEDIA_FORMAT_PROMPT
        self.parser = StrOutputParser()

    async def arun(self, state: MediaState) -> MediaState:
        visual_lines = []
        for visual in state.visuals:
            visual_lines.append(f"- {visual.title} ({visual.url})")
        state.report_markdown = await (self.prompt | self.llm | self.parser).ainvoke(
            {
                "query": state.query,
                "highlights": "\n".join(state.highlights) or "暂无",
                "risks": "\n".join(state.risks) or "暂无",
                "sentiment": state.sentiment or "未能确定整体情绪。",
                "visuals": "\n".join(visual_lines) or "暂无",
            }
        )
        state.record_event(self.name, "markdown report generated")
        return state

