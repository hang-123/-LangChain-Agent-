"""SearchOrchestrator Tool — delegates to existing search_agent logic.
Phase 2 wraps the SearchAgent as a Tool with structured interface.
Reuses core search logic from api/agents/search_agent.py."""

from __future__ import annotations

from typing import Any

from api.agents.search_agent import search_agent_node as _legacy_search
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

    # Phase 2: Auto-writeback high-quality results to RAG
    if settings.enable_rag and settings.enable_rag_writeback:
        try:
            from api.core.rag_store import auto_writeback
            evidence_items = result.get("evidence_items", [])
            if evidence_items:
                auto_writeback(evidence_items, settings.rag_writeback_quality_threshold)
        except Exception:
            pass  # Writeback failure is non-blocking

    return result
