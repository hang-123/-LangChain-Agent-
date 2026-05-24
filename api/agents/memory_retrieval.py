"""MemoryRetrievalNode — retrieves relevant memories before search.

Placed after IntentRouterNode and before SearchAgent in the graph.
Loads STM context and queries LTM for semantically related past evaluations.
"""

from __future__ import annotations

from typing import Any

from api.core.memory.retrieval import retrieve_memories
from api.core.memory.stm_store import build_conversation_memory_store
from api.core.memory.ltm_store import build_ltm_store
from api.core.settings import get_settings


async def memory_retrieval_node(state: dict[str, Any]) -> dict[str, Any]:
    """Retrieve relevant memories and inject them into the agent state.

    Reads query_profile from the state (set by IntentRouterNode),
    queries STM for recent turns and LTM for related historical evaluations,
    and injects formatted memory context into the state.

    When memory is disabled or no user_id is present, this is a no-op.
    """
    user_id = str(state.get("user_id") or "").strip()
    if not user_id:
        return _empty_result()

    settings = get_settings()
    if not settings.enable_conversation_memory:
        return _empty_result()

    query = str(state.get("query") or "")
    query_profile = dict(state.get("query_profile") or {})

    stm_store = build_conversation_memory_store()
    ltm_store = build_ltm_store()

    # Build vector_search_fn if pgvector is available on LTM store
    vector_search_fn = None
    if ltm_store is not None and hasattr(ltm_store, 'search_by_vector'):
        async def _vector_search(q: str, uid: str, k: int) -> list:
            from api.core.memory.models import LongTermMemory, MemoryHit, MemoryType, SourceType
            rows = await ltm_store.search_by_vector(q, uid, k)
            hits: list = []
            for row in rows:
                mem = LongTermMemory(
                    memory_id=row["memory_id"],
                    user_id=row["user_id"],
                    memory_type=MemoryType.SEMANTIC,
                    source_type=SourceType(row.get("source_type", "evaluation_report")),
                    content=row["chunk_text"],
                    importance=0.5,
                )
                hits.append(MemoryHit(
                    memory=mem,
                    score=row["score"],
                    retrieval_method="vector",
                ))
            return hits
        vector_search_fn = _vector_search

    memory_context = await retrieve_memories(
        ltm_store=ltm_store,
        stm_store=stm_store,
        query=query,
        query_profile=query_profile,
        user_id=user_id,
        top_k=5,
        vector_search_fn=vector_search_fn,  # pgvector semantic search
    )

    if memory_context.hit_count == 0:
        return _empty_result()

    # Inject memory hits into state — distributed by type for targeted agent use
    working_memory = list(state.get("working_memory") or [])

    memory_hits = [
        {
            "memory_id": hit.memory.memory_id,
            "memory_type": hit.memory.memory_type.value,
            "source_type": hit.memory.source_type.value,
            "content": hit.memory.content,
            "score": round(hit.score, 3),
            "retrieval_method": hit.retrieval_method,
        }
        for hit in memory_context.hits
    ]
    working_memory.append({
        "source": "memory_retrieval",
        "hits_count": memory_context.hit_count,
        "retrieval_time_ms": memory_context.retrieval_time_ms,
    })

    # Build typed context for distributed injection:
    #   entity_knowledge → SearchAgent query expansion
    #   pattern → Supervisor routing
    #   preference → Supervisor + Gate
    #   semantic → AnalysisAgent / ReportAgent
    #   episodic → [SYSTEM MEMORY] block (shared context)
    new_context: list[str] = []
    if memory_context.formatted_text:
        new_context.append(memory_context.formatted_text)

    entity_context = _build_entity_context(memory_context.entity_hits)
    pattern_context = _build_pattern_context(memory_context.pattern_hits)
    preference_context = _build_preference_context(memory_context.preference_hits)
    semantic_context = _build_semantic_context(memory_context.semantic_hits)

    return {
        "working_memory": working_memory,
        "memory_hits": memory_hits,
        "context": new_context,
        # Typed memory channels for downstream agents
        "entity_knowledge_memory": entity_context,
        "pattern_memory": pattern_context,
        "preference_memory": preference_context,
        "semantic_memory": semantic_context,
    }


def _build_entity_context(hits: list) -> dict[str, Any]:
    """Build entity knowledge context for SearchAgent query expansion."""
    companies: set[str] = set()
    tech_stacks: set[str] = set()
    for hit in hits:
        sd = hit.memory.structured_data if hasattr(hit.memory, 'structured_data') else {}
        company = sd.get("company", "")
        if company:
            companies.add(company)
        # Extract tech hints from content
        content = hit.memory.content.lower() if hasattr(hit.memory, 'content') else ""
        for tech in ["go", "python", "java", "rust", "c++", "k8s", "docker", "aws", "gcp"]:
            if tech in content:
                tech_stacks.add(tech)
    return {
        "known_companies": list(companies)[:5],
        "known_tech_stacks": list(tech_stacks)[:5],
        "hit_count": len(hits),
    }


def _build_pattern_context(hits: list) -> dict[str, Any]:
    """Build user pattern context for Supervisor routing."""
    roles: list[str] = []
    domains: list[str] = []
    for hit in hits:
        content = hit.memory.content if hasattr(hit.memory, 'content') else ""
        sd = hit.memory.structured_data if hasattr(hit.memory, 'structured_data') else {}
        role = sd.get("role", "")
        if role:
            roles.append(role)
        archetype = sd.get("archetype", "")
        if archetype:
            domains.append(archetype)
    return {
        "frequent_roles": roles[:3],
        "frequent_domains": domains[:3],
        "hit_count": len(hits),
    }


def _build_preference_context(hits: list) -> dict[str, Any]:
    """Build preference context for Gate / Supervisor."""
    prefs: dict[str, Any] = {}
    for hit in hits:
        content = hit.memory.content if hasattr(hit.memory, 'content') else ""
        prefs["summary"] = content[:200]
    prefs["hit_count"] = len(hits)
    return prefs


def _build_semantic_context(hits: list) -> dict[str, Any]:
    """Build semantic knowledge context for AnalysisAgent / ReportAgent."""
    topics: list[str] = []
    for hit in hits:
        content = hit.memory.content[:120] if hasattr(hit.memory, 'content') else ""
        if content:
            topics.append(content)
    return {
        "knowledge_snippets": topics[:3],
        "hit_count": len(hits),
    }


def _empty_result() -> dict[str, Any]:
    return {
        "working_memory": [{"source": "memory_retrieval", "hits_count": 0}],
        "memory_hits": [],
    }
