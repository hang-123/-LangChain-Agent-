from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class ReportSource:
    label: str
    content: str


@dataclass
class ReportSection:
    title: str
    summary: str


@dataclass
class ReportState:
    query: str
    title: str = ""
    sources: List[ReportSource] = field(default_factory=list)
    sections: List[ReportSection] = field(default_factory=list)
    executive_summary: str = ""
    final_markdown: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    compiled_sources: str = ""

    def add_source(self, label: str, content: str) -> None:
        if content:
            self.sources.append(ReportSource(label=label, content=content))
