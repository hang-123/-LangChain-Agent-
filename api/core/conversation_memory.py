"""Conversation Memory facade — backward-compatible API over api.core.memory.

Existing callers (executor, tests) use:
  - ConversationMemorySnapshot(user_id, conversation_id, summary, artifact_refs, updated_at)
  - build_turn_summary(query, state) → TurnSummary (with .summary and .artifact_refs)
  - load_memory_for_user(store, user_id) → ConversationMemorySnapshot | None
  - save_memory_turn(store, user_id, query, state) → TurnSummary | None

New code should import from api.core.memory directly for the enhanced API.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.core.memory.stm_store import (
    ConversationMemoryStore,
    build_conversation_memory_store,
)


# -- Backward-compatible ConversationMemorySnapshot --


class ConversationMemorySnapshot(BaseModel):
    """Deprecated snapshot class (kept for test compatibility).

    New code should use TurnSummary from api.core.memory.models.
    """

    user_id: str = ""
    conversation_id: str = ""
    summary: str = ""
    artifact_refs: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


# -- Old build_turn_summary (backward-compatible) --


def build_turn_summary(*, query: str, state: dict[str, Any]) -> ConversationMemorySnapshot:
    """Build a ConversationMemorySnapshot from completed agent state.

    Extracts artifact refs (job_snapshot_id, match_assessment_id, resume_version_id)
    from the state and builds a summary string.
    """
    # Extract artifact IDs
    artifact_refs = {
        "job_snapshot_id": _artifact_id(state, "job_snapshot", "job_snapshot_id"),
        "match_assessment_id": _artifact_id(state, "match_assessment", "assessment_id"),
        "resume_version_id": _artifact_id(state, "resume_version", "resume_version_id"),
    }
    artifact_refs = {key: value for key, value in artifact_refs.items() if value}

    # Build summary string
    match_assessment = dict(state.get("match_assessment") or {})
    resume_version = dict(state.get("resume_version") or {})
    summary_parts = [f"用户上一轮请求：{query}"]
    if match_assessment.get("recommendation"):
        summary_parts.append(f"匹配建议：{match_assessment['recommendation']}")
    if resume_version.get("fact_check_status"):
        summary_parts.append(f"简历事实校验：{resume_version['fact_check_status']}")

    return ConversationMemorySnapshot(
        user_id=str(state.get("user_id") or ""),
        conversation_id=f"conv::{state.get('user_id', '')}",
        summary="；".join(summary_parts),
        artifact_refs=artifact_refs,
        updated_at=str(state.get("updated_at") or ""),
    )


def _artifact_id(state: dict[str, Any], key: str, id_key: str) -> str:
    value = state.get(key) or {}
    return str(value.get(id_key) or "") if isinstance(value, dict) else ""


# -- Backward-compatible load/save --


async def load_memory_for_user(
    *,
    store: ConversationMemoryStore | None,
    user_id: str,
) -> ConversationMemorySnapshot | None:
    """Load the latest conversation snapshot for a user.

    Returns None if no memory exists, user_id is blank, or store is None.
    Handles both old (load_latest) and new (load_latest_summary) store interfaces.
    """
    clean_user_id = str(user_id or "").strip()
    if not clean_user_id or store is None:
        return None
    try:
        # Try new interface first (returns TurnSummary)
        if hasattr(store, "load_latest_summary"):
            summary = await store.load_latest_summary(clean_user_id)
            if summary is None:
                return None
            return ConversationMemorySnapshot(
                user_id=clean_user_id,
                conversation_id=f"conv::{clean_user_id}",
                summary=summary.model_dump_json() if hasattr(summary, "model_dump_json") else str(summary),
                artifact_refs=getattr(summary, "artifacts", {}),
                updated_at="",
            )
        # Fall back to old interface (returns ConversationMemorySnapshot directly)
        if hasattr(store, "load_latest"):
            return await store.load_latest(clean_user_id)
        return None
    except Exception:
        return None


async def save_memory_turn(
    *,
    store: ConversationMemoryStore | None,
    user_id: str,
    query: str,
    state: dict[str, Any],
) -> ConversationMemorySnapshot | None:
    """Save a turn to the memory store. Returns the snapshot or None on failure.

    Handles both old (save_turn with summary str) and new (save_turn with TurnSummary) interfaces.
    """
    clean_user_id = str(user_id or "").strip()
    if not clean_user_id or store is None:
        return None
    snapshot = build_turn_summary(query=query, state=state)
    try:
        # Try new interface: save_turn with session management
        if hasattr(store, "ensure_session"):
            await store.save_turn(
                user_id=clean_user_id,
                session_id=await store.ensure_session(clean_user_id),
                run_id=str(state.get("run_id") or ""),
                query=query,
                summary=_snapshot_to_new_summary(snapshot),
                artifacts=snapshot.artifact_refs,
            )
        else:
            # Old interface: save_turn with summary str
            await store.save_turn(
                user_id=clean_user_id,
                query=query,
                run_id=str(state.get("run_id") or ""),
                summary=snapshot.summary,
                artifact_refs=snapshot.artifact_refs,
            )
    except Exception:
        return None
    return snapshot


def _snapshot_to_new_summary(snapshot: ConversationMemorySnapshot) -> Any:
    """Convert old snapshot to new TurnSummary for store compatibility."""
    from api.core.memory.models import TurnSummary
    return TurnSummary(
        query=snapshot.summary,
        artifacts=snapshot.artifact_refs,
    )


__all__ = [
    "ConversationMemorySnapshot",
    "ConversationMemoryStore",
    "build_conversation_memory_store",
    "build_turn_summary",
    "load_memory_for_user",
    "save_memory_turn",
]
