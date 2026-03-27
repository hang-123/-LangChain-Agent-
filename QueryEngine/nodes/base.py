from __future__ import annotations

from typing import Protocol

from ..state import AgentState


class BaseNode(Protocol):
    """
    Async node protocol to keep the QueryAgent pipeline modular.
    Each node takes and returns AgentState, allowing composition.
    """

    name: str

    async def arun(self, state: AgentState) -> AgentState:  # pragma: no cover - interface
        ...
