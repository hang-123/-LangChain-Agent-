"""Memory Retrieval Pipeline — hybrid search across memory stores.

Combines:
  1. Structured filtering (tags, memory_type, recency)
  2. Keyword matching (exact company/role hits)
  3. Vector semantic search (via pgvector, when available)
  4. Reciprocal Rank Fusion for result merging
"""

from __future__ import annotations

import time
from typing import Any

from api.core.memory.models import (
    LongTermMemory,
    MemoryContext,
    MemoryHit,
    MemoryType,
    extract_keywords,
)
from api.core.memory.ltm_store import LongTermMemoryStore


# -- Reciprocal Rank Fusion --


def reciprocal_rank_fusion(
    *result_lists: list[MemoryHit],
    k: int = 60,
) -> list[MemoryHit]:
    """Merge multiple ranked result lists using RRF.

    Each hit's score is updated to sum(1 / (k + rank)) across all lists
    where it appears. Ties are broken by the original max score.
    """
    score_map: dict[str, tuple[float, float, MemoryHit]] = {}

    for hits in result_lists:
        for rank, hit in enumerate(hits, start=1):
            rrf_score = 1.0 / (k + rank)
            mem_id = hit.memory.memory_id
            if mem_id in score_map:
                accumulated, orig_max, existing = score_map[mem_id]
                score_map[mem_id] = (
                    accumulated + rrf_score,
                    max(orig_max, hit.score),
                    existing,
                )
            else:
                score_map[mem_id] = (rrf_score, hit.score, hit)

    merged: list[MemoryHit] = []
    for mem_id, (acc, orig, hit) in score_map.items():
        hit.score = acc
        hit.retrieval_method = "hybrid"
        merged.append(hit)

    merged.sort(key=lambda h: h.score, reverse=True)
    return merged


# -- Reranker --


def rerank_by_recency_importance(hits: list[MemoryHit]) -> list[MemoryHit]:
    """Boost recent and important memories.

    Final score = 0.5 * relevance + 0.3 * importance + 0.2 * recency_boost
    """
    now_iso = time.time()
    for hit in hits:
        importance = hit.memory.importance
        recency_boost = 0.5  # default for unknown dates
        if hit.memory.created_at:
            try:
                # Parse ISO date, compute days age
                created = hit.memory.created_at[:10]  # YYYY-MM-DD
                from datetime import datetime
                created_dt = datetime.strptime(created, "%Y-%m-%d")
                days_old = max(0, (datetime.now() - created_dt).days)
                if days_old < 7:
                    recency_boost = 1.0
                elif days_old < 30:
                    recency_boost = 0.8
                elif days_old < 90:
                    recency_boost = 0.5
                else:
                    recency_boost = 0.2
            except (ValueError, IndexError):
                pass
        hit.score = 0.5 * hit.score + 0.3 * importance + 0.2 * recency_boost

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


# -- Main Retrieval Pipeline --


async def retrieve_memories(
    *,
    ltm_store: LongTermMemoryStore | None,
    stm_store: Any | None,
    query: str,
    query_profile: dict[str, Any],
    user_id: str,
    top_k: int = 5,
    vector_search_fn: Any | None = None,
) -> MemoryContext:
    """Hybrid memory retrieval pipeline.

    Args:
        ltm_store: Long-term memory store for structured/keyword search.
        stm_store: Short-term memory store for recent turn context.
        query: The user's raw query text.
        query_profile: Structured query info {company, role, team_hint, ...}.
        user_id: The user identifier.
        top_k: Number of results to return.
        vector_search_fn: Optional async fn(query, user_id, top_k) -> list[MemoryHit].

    Returns:
        MemoryContext with hits and formatted text ready for agent injection.
    """
    t0 = time.perf_counter()

    if ltm_store is None:
        return MemoryContext()

    company = str(query_profile.get("company") or "")
    role = str(query_profile.get("role") or "")
    query_keywords = extract_keywords(query) + extract_keywords(f"{company} {role}")

    # --- 1. Structured Filter Retrieval ---
    structured_hits: list[MemoryHit] = []
    try:
        memories = await ltm_store.search_by_user(
            user_id,
            min_importance=0.2,
            limit=top_k * 3,
        )
        for mem in memories:
            score = _structured_score(mem, company, role, query_keywords)
            if score > 0:
                structured_hits.append(MemoryHit(
                    memory=mem,
                    score=score,
                    retrieval_method="keyword",
                ))
    except Exception:
        pass

    structured_hits.sort(key=lambda h: h.score, reverse=True)

    # --- 2. Vector Semantic Search ---
    vector_hits: list[MemoryHit] = []
    if vector_search_fn is not None:
        try:
            vector_hits = await vector_search_fn(query, user_id, top_k * 2)
        except Exception:
            pass

    # --- 3. STM Recent Context ---
    stm_hits: list[MemoryHit] = []
    if stm_store is not None:
        try:
            turns = await stm_store.load_turns(user_id, limit=3)
            for turn in turns:
                if turn.summary.company or turn.summary.role:
                    stm_score = _structured_score_turn(
                        turn.summary, company, role, query_keywords
                    )
                    if stm_score > 0.1:
                        # Convert turn to a synthetic LongTermMemory
                        synthetic_mem = LongTermMemory(
                            memory_id=f"stm-{turn.turn_id}",
                            user_id=user_id,
                            memory_type=MemoryType.EPISODIC,
                            source_type="evaluation_report",
                            content=(
                                f"Recent: {turn.summary.company} {turn.summary.role} "
                                f"(score: {turn.summary.overall_score}). "
                                f"{'; '.join(turn.summary.key_findings)}"
                            ),
                            importance=0.8,  # Recent STM is important
                            created_at=turn.created_at or "",
                        )
                        stm_hits.append(MemoryHit(
                            memory=synthetic_mem,
                            score=stm_score * 0.9,  # slightly discount vs LTM
                            retrieval_method="keyword",
                        ))
        except Exception:
            pass

    # --- 4. Merge & Rerank ---
    merged = reciprocal_rank_fusion(structured_hits, vector_hits, stm_hits)
    reranked = rerank_by_recency_importance(merged)
    final_hits = reranked[:top_k]

    # Update access counts
    for hit in final_hits:
        if not hit.memory.memory_id.startswith("stm-"):
            try:
                await ltm_store.update_access(hit.memory.memory_id)
            except Exception:
                pass

    elapsed_ms = (time.perf_counter() - t0) * 1000
    formatted = _format_memory_context(final_hits)
    typed = _group_by_type(final_hits)

    return MemoryContext(
        hits=final_hits,
        formatted_text=formatted,
        hit_count=len(final_hits),
        retrieval_time_ms=round(elapsed_ms, 2),
        entity_hits=typed.get(MemoryType.ENTITY_KNOWLEDGE, []),
        pattern_hits=typed.get(MemoryType.PATTERN, []),
        preference_hits=typed.get(MemoryType.PREFERENCE, []),
        semantic_hits=typed.get(MemoryType.SEMANTIC, []),
        episodic_hits=typed.get(MemoryType.EPISODIC, []),
    )


# -- Scoring Helpers --


def _structured_score(
    mem: LongTermMemory,
    company: str,
    role: str,
    keywords: list[str],
) -> float:
    """Score a memory against query parameters. Returns 0.0-1.0."""
    score = 0.0
    content_lower = mem.content.lower()

    # Exact company match = strong signal
    if company and company.lower() in content_lower:
        score += 0.4

    # Role keyword overlap
    if role:
        role_words = extract_keywords(role)
        role_hits = sum(1 for w in role_words if w in content_lower)
        if role_words:
            score += 0.3 * (role_hits / len(role_words))

    # Generic keyword overlap
    kw_hits = sum(1 for kw in keywords if kw in content_lower)
    if keywords:
        score += 0.2 * (kw_hits / len(keywords))

    # Memory type bonus: semantic preferences are always relevant
    if mem.memory_type == MemoryType.SEMANTIC:
        score += 0.1

    return min(score, 1.0)


def _structured_score_turn(
    summary: Any,
    company: str,
    role: str,
    keywords: list[str],
) -> float:
    """Score a TurnSummary against query parameters."""
    score = 0.0
    summ_company = (summary.company or "").lower()
    summ_role = (summary.role or "").lower()
    summ_text = f"{summ_company} {summ_role} {' '.join(summary.key_findings)}".lower()

    if company and company.lower() in summ_company:
        score += 0.4
    if role:
        role_words = extract_keywords(role)
        role_hits = sum(1 for w in role_words if w in summ_role)
        if role_words:
            score += 0.3 * (role_hits / len(role_words))
    kw_hits = sum(1 for kw in keywords if kw in summ_text)
    if keywords:
        score += 0.2 * (kw_hits / len(keywords))

    return min(score, 1.0)


# -- Context Formatting --


def _format_memory_context(hits: list[MemoryHit]) -> str:
    """Format memory hits as injectable agent context."""
    if not hits:
        return ""

    lines = [
        "[SYSTEM MEMORY — relevant information from your past sessions]\n",
    ]
    for i, hit in enumerate(hits, start=1):
        mem = hit.memory
        age_hint = _age_hint(mem.created_at) if mem.created_at else ""
        lines.append(
            f"{i}. [{mem.memory_type.value} | {mem.source_type.value}] "
            f"{mem.content}"
            f"{' (' + age_hint + ')' if age_hint else ''}"
        )
    lines.append("\n[END MEMORY]\n")
    return "\n".join(lines)


def _age_hint(created_at: str) -> str:
    """Human-readable age from ISO timestamp."""
    try:
        from datetime import datetime
        created = datetime.strptime(created_at[:10], "%Y-%m-%d")
        days = max(0, (datetime.now() - created).days)
        if days == 0:
            return "today"
        if days == 1:
            return "yesterday"
        if days < 7:
            return f"{days}d ago"
        if days < 30:
            return f"{days // 7}w ago"
        if days < 365:
            return f"{days // 30}mo ago"
        return f"{days // 365}y ago"
    except (ValueError, IndexError):
        return ""


def _group_by_type(hits: list[MemoryHit]) -> dict[MemoryType, list[MemoryHit]]:
    """Group hits by memory type for distributed injection."""
    groups: dict[MemoryType, list[MemoryHit]] = {}
    for hit in hits:
        groups.setdefault(hit.memory.memory_type, []).append(hit)
    return groups
