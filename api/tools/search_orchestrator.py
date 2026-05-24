"""SearchOrchestrator Tool — delegates to existing search_agent logic.
Phase 2 wraps the SearchAgent as a Tool with structured interface.
Reuses core search logic from api/agents/search_agent.py."""

from __future__ import annotations

from typing import Any

from api.agents.search_agent import search_agent_node as _legacy_search
from api.core.harness import utc_now_iso
from api.core.job_query import build_query_profile
from api.core.settings import get_settings


async def run_search_orchestrator(state: dict[str, Any]) -> dict[str, Any]:
    """SearchOrchestrator Tool — search orchestration with caching and RAG.

    Delegates to the existing search_agent_node for the heavy lifting.
    Adds Phase 2 auto-writeback of high-quality results to RAG.
    """
    settings = get_settings()

    # Ensure query_profile exists
    if not state.get("query_profile"):
        state["query_profile"] = build_query_profile(
            str(state.get("query", "")),
            intent=str(state.get("intent", "general")),
        )

    # Run existing search logic
    result = await _legacy_search(state)

    # Phase 2: Auto-writeback high-quality results to RAG + LTM bridge
    if settings.enable_rag and settings.enable_rag_writeback:
        try:
            from api.core.rag_store import auto_writeback
            evidence_items = result.get("evidence_items", [])
            if evidence_items:
                await auto_writeback(
                    evidence_items,
                    settings.rag_writeback_quality_threshold,
                    profile=query_profile,
                    user_id=str(state.get("user_id") or ""),
                )
        except Exception:
            pass  # Writeback failure is non-blocking

    # Phase 2: working memory entry
    evidence_items = result.get("evidence_items", [])
    retrieval_diagnostics = result.get("retrieval_diagnostics", {})
    query_pack = result.get("query_pack", [])
    working_memory = list(state.get("working_memory") or [])
    evidence_count = len(evidence_items)
    company_specific_count = sum(1 for e in evidence_items if e.get("company_specific"))
    source_urls = [e.get("url", "") for e in evidence_items if e.get("url")]
    working_memory.append({
        "source": "search_orchestrator",
        "summary": {
            "evidence_count": evidence_count,
            "company_specific_count": company_specific_count,
            "source_urls": source_urls[:10],
            "query_pack_size": len(query_pack),
            "cached": bool(retrieval_diagnostics.get("cached")),
        },
        "timestamp": utc_now_iso(),
    })
    result["working_memory"] = working_memory

    return result
