"""
ReportAgent composes a final markdown deliverable from upstream agents.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

from .config import ReportEngineConfig
from .nodes import PlanNode, RenderNode, SourceGatherNode
from .state import ReportSource, ReportState
from utils.logger import log_agent_run


@dataclass
class ReportAgentResult:
    markdown: str
    state: ReportState
    report_file: Optional[Path]


class ReportAgent:
    def __init__(self, config: Optional[ReportEngineConfig] = None):
        self.config = config or ReportEngineConfig.from_env()
        self.nodes = [
            SourceGatherNode(),
            PlanNode(self.config),
            RenderNode(self.config),
        ]

    def run(
        self,
        query: str,
        sources: Iterable[Tuple[str, str]],
        save_report: bool = True,
    ) -> ReportAgentResult:
        return asyncio.run(self._arun(query, sources, save_report))

    async def _arun(
        self,
        query: str,
        sources: Iterable[Tuple[str, str]],
        save_report: bool,
    ) -> ReportAgentResult:
        state = ReportState(query=query)
        for label, content in sources:
            state.add_source(label, content)

        for node in self.nodes:
            state = await node.arun(state)
        summary = state.final_markdown[:200] + "..." if state.final_markdown else "No final report generated."
        log_agent_run("report", query, summary=summary)

        report_path = None
        if save_report:
            report_path = self._save_report(state)

        return ReportAgentResult(markdown=state.final_markdown, state=state, report_file=report_path)

    def _save_report(self, state: ReportState) -> Path:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        safe_query = "".join(c for c in state.query if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        filename = f"executive_report_{safe_query}_{state.created_at.replace(':', '').replace('-', '')}.md"
        path = self.config.output_dir / filename
        path.write_text(state.final_markdown, encoding="utf-8")
        return path
