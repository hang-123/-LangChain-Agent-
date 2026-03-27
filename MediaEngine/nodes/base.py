from __future__ import annotations

from typing import Protocol

from ..state import MediaState


class MediaNode(Protocol):
    name: str

    async def arun(self, state: MediaState) -> MediaState:  # pragma: no cover - interface
        ...

