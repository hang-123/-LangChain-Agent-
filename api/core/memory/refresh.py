"""Stale-While-Revalidate refresh logic for LTM (v2.0).

When a memory reaches STALE threshold (importance ≤ 0.2):
  - ENTITY_KNOWLEDGE / SEMANTIC: trigger web search to verify/update content
  - EPISODE / PATTERN: continue decaying toward soft delete
  - PREFERENCE: never triggers
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from api.core.memory.models import LongTermMemory, MemoryStatus, MemoryType, SourceType
from api.core.memory.ltm_store import LongTermMemoryStore
from api.core.settings import get_settings


async def refresh_stale_memories(
    *,
    ltm_store: LongTermMemoryStore,
    user_id: str,
) -> dict[str, int]:
    """Find stale memories and attempt refresh.

    Returns {refreshed, failed, skipped}.
    """
    settings = get_settings()
    max_retries = int(settings.refresh_max_retries or 3)
    penalty = float(settings.refresh_failed_penalty or 0.5)

    result = {"refreshed": 0, "failed": 0, "skipped": 0}

    # Query stale memories eligible for refresh
    stale = await ltm_store.search_by_user(
        user_id,
        min_importance=0.01,
        limit=20,
    )
    stale = [m for m in stale if m.status == MemoryStatus.EXPIRED_PENDING_REFRESH]

    for mem in stale:
        if not mem.memory_type.supports_refresh:
            result["skipped"] += 1
            continue

        success = await _refresh_single(mem, ltm_store, max_retries, penalty)
        if success:
            result["refreshed"] += 1
        else:
            result["failed"] += 1

    return result


async def _refresh_single(
    mem: LongTermMemory,
    store: LongTermMemoryStore,
    max_retries: int,
    penalty: float,
) -> bool:
    """Attempt to refresh a single memory via web search.

    Returns True if refresh succeeded (content updated or verified unchanged).
    Returns False if refresh failed → apply penalty.
    """
    company = mem.structured_data.get("company", "") if mem.structured_data else ""
    source_type = mem.source_type.value if hasattr(mem.source_type, 'value') else str(mem.source_type)

    if mem.refresh_attempts >= max_retries:
        # Too many failures → soft delete
        await store.save(_update_memory(mem, status=MemoryStatus.SOFT_DELETED))
        return False

    # Attempt web search refresh
    new_content = await _search_refresh(company=company, source_type=source_type)
    if new_content is None:
        # Refresh failed
        new_importance = round(mem.importance * penalty, 4)
        await store.save(_update_memory(
            mem,
            importance=new_importance,
            status=MemoryStatus.REFRESH_FAILED if new_importance > 0.1 else MemoryStatus.SOFT_DELETED,
            refresh_attempts=mem.refresh_attempts + 1,
            last_refreshed_at=datetime.utcnow().isoformat(),
        ))
        return False

    # Compare content
    new_hash = hashlib.md5(new_content.encode()).hexdigest()[:12]
    if new_hash == mem.content_hash:
        # Content unchanged — just reset expiry
        lifetime = mem.memory_type.lifetime_days or 180
        await store.save(_update_memory(
            mem,
            importance=mem.initial_importance,
            status=MemoryStatus.ACTIVE,
            refresh_attempts=0,
            last_refreshed_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(days=lifetime)).isoformat(),
        ))
    else:
        # Content updated
        lifetime = mem.memory_type.lifetime_days or 180
        await store.save(_update_memory(
            mem,
            content=new_content,
            content_hash=new_hash,
            importance=mem.initial_importance,
            status=MemoryStatus.ACTIVE,
            refresh_attempts=0,
            last_refreshed_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(days=lifetime)).isoformat(),
        ))
    return True


async def _search_refresh(*, company: str, source_type: str) -> str | None:
    """Search the web to verify/update stale entity knowledge.

    Uses Tavily API for a quick search. Returns None on failure.
    """
    if not company:
        return None
    try:
        from api.core.settings import get_settings
        settings = get_settings()
        api_key = (
            settings.tavily_api_key.get_secret_value()
            if settings.tavily_api_key else ""
        )
        if not api_key:
            return None

        query_map = {
            "evaluation_report": f"{company} 公司 招聘 技术栈",
            "interview_exp": f"{company} 面试 面经",
            "system_observation": f"{company} 公司 工作",
            "rag_writeback": f"{company} {source_type}",
        }
        query = query_map.get(source_type, f"{company} 公司")

        from api.tools.tavily_searcher import search_tavily_queries
        results = await search_tavily_queries(
            queries=[query],
            max_results=3,
            search_depth="basic",
        )
        sources = results.get("sources", []) or []
        if sources:
            snippets = [s.get("snippet", "") or s.get("content", "") for s in sources[:2]]
            return " | ".join(s for s in snippets if s)
        return None
    except Exception:
        return None


def _update_memory(mem: LongTermMemory, **overrides) -> LongTermMemory:
    """Create an updated copy of a memory with overridden fields."""
    data = {
        "memory_id": mem.memory_id,
        "user_id": mem.user_id,
        "memory_type": mem.memory_type,
        "source_type": mem.source_type,
        "content": mem.content,
        "structured_data": mem.structured_data,
        "initial_importance": mem.initial_importance,
        "importance": mem.importance,
        "lifetime_days": mem.lifetime_days,
        "access_count": mem.access_count,
        "status": mem.status,
        "content_hash": mem.content_hash,
        "refresh_attempts": mem.refresh_attempts,
        "last_accessed_at": mem.last_accessed_at,
        "last_refreshed_at": mem.last_refreshed_at,
        "created_at": mem.created_at,
        "expires_at": mem.expires_at,
    }
    data.update(overrides)
    return LongTermMemory(**data)
