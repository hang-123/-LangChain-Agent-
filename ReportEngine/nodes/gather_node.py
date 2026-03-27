from __future__ import annotations

from ..state import ReportState
from .base import ReportNode


class SourceGatherNode(ReportNode):
    name = "source_gather"

    async def arun(self, state: ReportState) -> ReportState:
        if not state.title:
            state.title = f"{state.query} 求职研究报告"
        parts = []
        for source in state.sources:
            parts.append(f"[{source.label}]\n{source.content}")
        state.compiled_sources = "\n\n".join(parts) or "暂无外部输入。"
        return state
