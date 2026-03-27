from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class MediaAsset:
    title: str
    url: str
    description: str
    published_date: Optional[str] = None
    image_url: Optional[str] = None


@dataclass
class MediaState:
    query: str
    articles: List[MediaAsset] = field(default_factory=list)
    visuals: List[MediaAsset] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    sentiment: str = ""
    report_markdown: str = ""
    events: List["MediaEvent"] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def record_event(self, stage: str, detail: str) -> None:
        self.events.append(MediaEvent(stage=stage, detail=detail))


@dataclass
class MediaEvent:
    stage: str
    detail: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

