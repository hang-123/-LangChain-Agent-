from __future__ import annotations

from typing import Protocol

from ..state import ReportState


class ReportNode(Protocol):
    name: str

    async def arun(self, state: ReportState) -> ReportState:  # pragma: no cover
        ...

