"""
Tavily search helpers that mirror the toolbox from the original project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from tavily import TavilyClient

from ..state import SearchResult
from utils.retry_helper import SEARCH_API_RETRY_CONFIG, with_retry


@dataclass
class TavilyResponse:
    query: str
    tool_name: str
    results: List[SearchResult]

    def deduplicated(self, *, max_results: int = 8) -> "TavilyResponse":
        """
        简单去重并裁剪结果数量，用于减少重复网页和 token 消耗。
        """

        seen_urls = set()
        seen_titles = set()
        deduped: List[SearchResult] = []
        for item in self.results:
            key_url = (item.url or "").strip()
            key_title = (item.title or "").strip()
            if key_url and key_url in seen_urls:
                continue
            if key_title and key_title in seen_titles:
                continue
            if key_url:
                seen_urls.add(key_url)
            if key_title:
                seen_titles.add(key_title)
            deduped.append(item)
            if len(deduped) >= max_results:
                break
        return TavilyResponse(query=self.query, tool_name=self.tool_name, results=deduped)


class TavilyToolset:
    def __init__(self, api_key: str):
        self._client = TavilyClient(api_key=api_key)

    @with_retry(SEARCH_API_RETRY_CONFIG)
    def _search(self, query: str, tool_name: str, *, use_image_results: bool = False, **kwargs) -> TavilyResponse:
        response = self._client.search(query=query, **kwargs)
        payload_key = "images" if use_image_results else "results"
        items = response.get(payload_key, [])
        if use_image_results:
            results = [
                SearchResult(
                    title=item.get("title") or item.get("source") or "image",
                    url=item.get("url", ""),
                    content=item.get("description", ""),
                )
                for item in items
            ]
        else:
            results = [
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    published_date=item.get("published_date"),
                    score=item.get("score"),
                )
                for item in items
            ]
        return TavilyResponse(query=query, tool_name=tool_name, results=results)

    def basic_search(self, query: str, max_results: int = 7) -> TavilyResponse:
        resp = self._search(
            query,
            "basic_search_news",
            max_results=max_results,
            search_depth="basic",
            include_answer=False,
            topic="news",
        )
        return resp.deduplicated(max_results=max_results)

    def deep_search(self, query: str, max_results: int = 20) -> TavilyResponse:
        resp = self._search(
            query,
            "deep_search_news",
            search_depth="advanced",
            max_results=max_results,
            include_answer="advanced",
            topic="news",
        )
        # 深度搜索默认也控制在较少的去重结果，防止段落研究阶段过长
        return resp.deduplicated(max_results=max_results)

    def last_24h(self, query: str, max_results: int = 12) -> TavilyResponse:
        resp = self._search(
            query,
            "search_news_last_24_hours",
            time_range="d",
            max_results=max_results,
            topic="news",
        )
        return resp.deduplicated(max_results=max_results)

    def last_week(self, query: str, max_results: int = 12) -> TavilyResponse:
        resp = self._search(
            query,
            "search_news_last_week",
            time_range="w",
            max_results=max_results,
            topic="news",
        )
        return resp.deduplicated(max_results=max_results)

    def search_images(self, query: str, max_results: int = 8) -> TavilyResponse:
        resp = self._search(
            query,
            "search_images_for_news",
            use_image_results=True,
            include_images=True,
            include_image_descriptions=True,
            max_results=max_results,
            topic="news",
        )
        return resp.deduplicated(max_results=max_results)

    def search_by_date(self, query: str, *, start_date: str, end_date: str, max_results: int = 20) -> TavilyResponse:
        resp = self._search(
            query,
            "search_news_by_date",
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
            search_depth="advanced",
            topic="news",
        )
        return resp.deduplicated(max_results=max_results)


# Optional internal vector search (PGVector)
class InternalVectorToolset:
    def __init__(self, k: int = 8):
        self.k = k
        try:
            from InsightEngine.tools.vector_store_pg import get_retriever  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Internal vector tool requires InsightEngine.tools.vector_store_pg") from e
        self._get_retriever = get_retriever

    def search(self, query: str) -> TavilyResponse:
        retriever = self._get_retriever(k=self.k)
        docs = retriever.invoke(query)
        results: List[SearchResult] = []
        for d in docs:
            meta = getattr(d, "metadata", {}) or {}
            src = meta.get("source") or "internal_doc"
            content = getattr(d, "page_content", "")
            results.append(
                SearchResult(
                    title=f"[{src}]",
                    url=meta.get("url", ""),
                    content=content,
                    published_date=meta.get("published_date"),
                    score=meta.get("score"),
                )
            )
        return TavilyResponse(query=query, tool_name="internal_vector_search", results=results)
