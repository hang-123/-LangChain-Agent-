from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List


@dataclass
class ForumMessage:
    speaker: str
    content: str
    metadata: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ForumSession:
    query: str
    session_id: str | None = None
    messages: List[ForumMessage] = field(default_factory=list)

    def add_message(
        self,
        speaker: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.messages.append(ForumMessage(speaker=speaker, content=content, metadata=metadata))
