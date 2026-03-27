from __future__ import annotations

from ..config import MediaEngineConfig
from ..state import MediaState
from ..tools import MediaToolset
from .base import MediaNode


class MediaSearchNode(MediaNode):
    name = "media_search"

    def __init__(self, tools: MediaToolset, config: MediaEngineConfig):
        self.tools = tools
        self.config = config

    async def arun(self, state: MediaState) -> MediaState:
        state.record_event(self.name, "fetching multimedia evidence")
        resp = self.tools.search(state.query)
        state.articles = resp.articles
        state.visuals = resp.visuals
        state.record_event(
            self.name, f"collected {len(resp.articles)} articles & {len(resp.visuals)} visuals"
        )
        return state

