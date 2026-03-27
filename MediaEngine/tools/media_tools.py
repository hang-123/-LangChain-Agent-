from __future__ import annotations

from dataclasses import dataclass
from typing import List

from QueryEngine.tools import TavilyToolset

from ..config import MediaEngineConfig
from ..state import MediaAsset


@dataclass
class MediaSearchResponse:
    articles: List[MediaAsset]
    visuals: List[MediaAsset]


class MediaToolset:
    """
    Thin wrapper around the QueryEngine Tavily tools to fetch long-form articles
    and supporting imagery for media briefs.
    """

    def __init__(self, config: MediaEngineConfig):
        self._tavily = TavilyToolset(api_key=config.tavily_api_key)  # type: ignore[arg-type]
        self.config = config

    def search(self, query: str) -> MediaSearchResponse:
        article_resp = self._tavily.deep_search(query, max_results=self.config.max_media_items)
        images_resp = (
            self._tavily.search_images(query, max_results=self.config.max_media_items // 2)
            if self.config.include_images
            else None
        )
        articles = [
            MediaAsset(
                title=result.title,
                url=result.url,
                description=result.content,
                published_date=result.published_date,
            )
            for result in article_resp.results
        ]
        visuals: List[MediaAsset] = []
        if images_resp:
            for result in images_resp.results:
                visuals.append(
                    MediaAsset(
                        title=result.title,
                        url=result.url,
                        description=result.content,
                    )
                )
        return MediaSearchResponse(articles=articles, visuals=visuals)

