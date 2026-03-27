"""
MediaEngine agent assembles multimedia search insights.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import MediaEngineConfig
from .nodes import MediaFormattingNode, MediaSearchNode, MediaSummaryNode
from .state import MediaState
from .tools import MediaToolset
from utils.logger import log_agent_run


@dataclass
class MediaAgentResult:
    report_markdown: str
    state: MediaState
    report_file: Optional[Path]


class MediaAgent:
    def __init__(self, config: Optional[MediaEngineConfig] = None):
        self.config = config or MediaEngineConfig.from_env()
        self.tools = MediaToolset(self.config)
        self.nodes = [
            MediaSearchNode(self.tools, self.config),
            MediaSummaryNode(self.config),
            MediaFormattingNode(self.config),
        ]

    def run(self, query: str, save_report: bool = True) -> MediaAgentResult:
        return asyncio.run(self._arun(query, save_report))

    async def _arun(self, query: str, save_report: bool) -> MediaAgentResult:
        state = MediaState(query=query)
        for node in self.nodes:
            state = await node.arun(state)
        summary = state.report_markdown[:200] + "..." if state.report_markdown else "No media brief generated."
        log_agent_run("media", query, summary=summary)

        report_path = None
        if save_report:
            report_path = self._save_report(state)

        return MediaAgentResult(report_markdown=state.report_markdown, state=state, report_file=report_path)

    def _save_report(self, state: MediaState) -> Path:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        safe_query = "".join(c for c in state.query if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        filename = f"media_brief_{safe_query}_{state.created_at.replace(':', '').replace('-', '')}.md"
        path = self.config.output_dir / filename
        path.write_text(state.report_markdown, encoding="utf-8")
        return path
