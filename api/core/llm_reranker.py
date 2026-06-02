"""Stage 2 Reranker: LLM-as-Reranker for fine-grained relevance scoring.

After Cross-Encoder coarse reranking, the LLM applies semantic understanding
to pick the most information-dense and query-relevant documents.
"""

from __future__ import annotations

import json
import re
from typing import Any


_RERANK_PROMPT = """You are a relevance scoring expert for a job research RAG system.

Query: {query}

Rate each candidate document below on a scale of 1-5 based on:
1. **Relevance**: Does it directly answer or relate to the query?
2. **Factual density**: Does it contain concrete facts, numbers, names, or specific details?
3. **Source authority**: Is the source likely reliable (official JD, company page, detailed interview)?

Return ONLY a JSON array. No explanation, no markdown fences:
[{{"index": 0, "score": 4, "reason": "Directly describes the team's tech stack"}}, ...]

Candidates:
{candidates}"""


async def _llm_rerank(
    query: str,
    documents: list[str],
    top_k: int = 5,
    *,
    model: Any | None = None,
) -> list[tuple[int, float, str]]:
    """Use LLM to score and rerank candidate documents.

    Args:
        query: The search query
        documents: Candidate document texts
        top_k: Number of top results to return
        model: Optional pre-configured chat model (lazy init if None)

    Returns:
        List of (original_index, score, reason) sorted by score desc
    """
    if not documents:
        return []

    # Format candidates for prompt
    candidates_str = "\n".join(
        f"[{i}] {doc[:300]}" for i, doc in enumerate(documents)
    )

    prompt = _RERANK_PROMPT.format(query=query, candidates=candidates_str)

    try:
        if model is None:
            from api.core.llm import get_chat_model
            model = get_chat_model(temperature=0.0)

        response = await model.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from response (robust to markdown fences)
        parsed = _parse_rerank_json(str(content))
        if not parsed:
            return [(i, 2.5, "default") for i in range(min(top_k, len(documents)))]

        # Sort by score desc, take top_k
        parsed.sort(key=lambda x: x.get("score", 2.5), reverse=True)
        result = [
            (int(item["index"]), float(item["score"]), str(item.get("reason", "")))
            for item in parsed[:top_k]
            if 0 <= int(item["index"]) < len(documents)
        ]
        return result if result else [
            (i, 2.5, "default") for i in range(min(top_k, len(documents)))
        ]

    except Exception:
        return [(i, 2.5, "default") for i in range(min(top_k, len(documents)))]


def _parse_rerank_json(text: str) -> list[dict]:
    """Parse JSON from LLM response, robust to markdown fences and partial output."""
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```", "", cleaned)

    # Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "results" in data:
            return data["results"]
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in text
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    return []


class LLMReranker:
    """LLM-based fine-grained reranker (Stage 2).

    Usage:
        reranker = LLMReranker()
        results = await reranker.rerank(query, documents, top_k=5)
        # results: [(original_index, score, reason), ...]
    """

    def __init__(self) -> None:
        self._model: Any | None = None

    async def rerank(
        self, query: str, documents: list[str], top_k: int = 5
    ) -> list[tuple[int, float, str]]:
        """Rerank documents using the LLM."""
        return await _llm_rerank(query, documents, top_k, model=self._model)

    async def rerank_hits(
        self,
        query: str,
        hits: list[Any],
        *,
        top_k: int = 5,
    ) -> list[Any]:
        """Rerank RagSearchHit objects using the LLM.

        Args:
            query: Search query
            hits: List of RagSearchHit from rag_store
            top_k: Number of top results to return

        Returns:
            Reranked list of RagSearchHit with updated scores
        """
        if not hits:
            return hits

        documents = [hit.chunk.text for hit in hits]
        reranked = await self.rerank(query, documents, top_k=min(top_k, len(hits)))

        result: list[Any] = []
        for orig_idx, score, _reason in reranked:
            if 0 <= orig_idx < len(hits):
                hit = hits[orig_idx]
                # Create a new hit with the LLM reranked score
                from dataclasses import replace
                try:
                    new_hit = replace(hit, score=score)
                except Exception:
                    new_hit = hit
                result.append(new_hit)
        return result


def build_llm_reranker() -> LLMReranker | None:
    """Build LLM reranker if enabled in settings."""
    from api.core.settings import get_settings

    settings = get_settings()
    if not settings.enable_llm_reranker:
        return None
    return LLMReranker()
