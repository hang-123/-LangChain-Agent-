"""
State objects used during a Query Agent run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    published_date: Optional[str] = None
    score: Optional[float] = None


@dataclass
class SearchHistory:
    query: str
    tool_used: str
    results: List[SearchResult]
    executed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ParagraphPlan:
    title: str
    expectation: str
    latest_summary: str = ""
    reflections: int = 0
    searches: List[SearchHistory] = field(default_factory=list)

    def add_search(self, history: SearchHistory) -> None:
        self.searches.append(history)


@dataclass
class AgentState:
    query: str
    paragraphs: List[ParagraphPlan] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    report_title: str = ""
    report_markdown: str = ""
    events: List["AgentEvent"] = field(default_factory=list)

    def add_paragraph(self, paragraph: ParagraphPlan) -> None:
        self.paragraphs.append(paragraph)

    def mark_completed(self) -> None:
        self.completed_at = datetime.utcnow().isoformat()

    def record_event(self, stage: str, detail: str) -> None:
        self.events.append(AgentEvent(stage=stage, detail=detail))

    def to_json(self) -> str:
        data: Dict[str, Any] = {
            "query": self.query,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "report_title": self.report_title,
            "report_markdown": self.report_markdown,
            "paragraphs": [
                {
                    "title": p.title,
                    "expectation": p.expectation,
                    "latest_summary": p.latest_summary,
                    "reflections": p.reflections,
                    "searches": [
                        {
                            "query": h.query,
                            "tool_used": h.tool_used,
                            "executed_at": h.executed_at,
                            "results": [r.__dict__ for r in h.results],
                        }
                        for h in p.searches
                    ],
                }
                for p in self.paragraphs
            ],
            "events": [
                {
                    "stage": event.stage,
                    "detail": event.detail,
                    "timestamp": event.created_at,
                }
                for event in self.events
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")


@dataclass
class AgentEvent:
    stage: str
    detail: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
