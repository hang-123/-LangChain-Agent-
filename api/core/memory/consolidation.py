"""Memory Consolidation — STM→LTM transfer, importance scoring, and decay.

Runs at session boundaries and periodically to maintain memory health.
"""

from __future__ import annotations

import uuid

from api.core.harness import utc_now_iso
from api.core.memory.ltm_store import LongTermMemoryStore
from api.core.memory.models import (
    LongTermMemory,
    MemoryType,
    SourceType,
    TurnRecord,
)
from api.core.memory.stm_store import ConversationMemoryStore


# -- Importance Scoring --


def score_importance(turn: TurnRecord) -> float:
    """Determine initial importance for a memory derived from a turn.

    Rules:
      - score >= 4.0 (high match) → 0.8
      - score >= 3.0 (medium match) → 0.5
      - score < 3.0 (low match) → 0.3
      - User gave explicit feedback → +0.15
      - Quality mode was conservative → +0.1 (system was uncertain, worth remembering)
    """
    base = 0.5
    s = turn.summary

    if s.overall_score is not None:
        if s.overall_score >= 4.0:
            base = 0.8
        elif s.overall_score >= 3.0:
            base = 0.5
        else:
            base = 0.3

    # Boost if there's substantial content (key findings)
    if len(s.key_findings) >= 3:
        base = min(1.0, base + 0.05)

    if s.quality_mode == "conservative":
        base = min(1.0, base + 0.1)

    return round(base, 2)


def classify_memory_type(turn: TurnRecord) -> MemoryType:
    """Classify a turn into the appropriate memory type."""
    s = turn.summary
    if s.overall_score is not None and s.recommendation:
        return MemoryType.EPISODIC
    if s.archetype:
        return MemoryType.SEMANTIC
    return MemoryType.EPISODIC


def classify_source_type(turn: TurnRecord) -> SourceType:
    """Classify the source of a memory."""
    s = turn.summary
    if s.overall_score is not None:
        return SourceType.EVALUATION_REPORT
    if any("interview" in f.lower() for f in s.key_findings):
        return SourceType.INTERVIEW_EXP
    return SourceType.SYSTEM_OBSERVATION


# -- Consolidation --


async def consolidate_session(
    *,
    stm_store: ConversationMemoryStore,
    ltm_store: LongTermMemoryStore,
    user_id: str,
    session_id: str,
) -> int:
    """Consolidate all turns from a STM session into LTM.

    Reads turns from the session, scores importance, and persists to LTM.
    Returns the number of memories created.
    """
    if ltm_store is None:
        return 0

    turns = await stm_store.load_turns(user_id, session_id=session_id, limit=100)
    if not turns:
        return 0

    created = 0
    for turn in turns:
        importance = score_importance(turn)
        if importance < 0.2:
            continue  # skip low-value turns

        memory = LongTermMemory(
            memory_id=f"mem-{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            memory_type=classify_memory_type(turn),
            source_type=classify_source_type(turn),
            content=_build_memory_content(turn),
            structured_data={
                "company": turn.summary.company,
                "role": turn.summary.role,
                "archetype": turn.summary.archetype,
                "score": turn.summary.overall_score,
                "recommendation": turn.summary.recommendation,
                "tags": turn.summary.tags,
                "run_id": turn.run_id,
                "session_id": turn.session_id,
            },
            importance=importance,
            created_at=turn.created_at or utc_now_iso(),
        )
        try:
            await ltm_store.save(memory)
            created += 1
        except Exception:
            continue

    # End the STM session after consolidation
    try:
        await stm_store.end_session(session_id)
    except Exception:
        pass

    return created


async def run_periodic_maintenance(
    *,
    ltm_store: LongTermMemoryStore,
    user_id: str,
) -> dict[str, int]:
    """Run periodic memory maintenance: decay + expire.

    Returns counts of {decayed, expired}.
    """
    result = {"decayed": 0, "expired": 0}
    if ltm_store is None:
        return result

    try:
        result["decayed"] = await ltm_store.apply_decay(user_id)
    except Exception:
        pass

    try:
        result["expired"] = await ltm_store.expire(user_id)
    except Exception:
        pass

    return result


# -- Content Builder --


def _build_memory_content(turn: TurnRecord) -> str:
    """Build a concise, searchable memory content string from a turn."""
    s = turn.summary
    parts: list[str] = []

    if s.company and s.role:
        parts.append(f"Evaluated {s.company} {s.role}")

    if s.overall_score is not None:
        parts.append(f"score {s.overall_score}/5")

    if s.archetype:
        parts.append(f"archetype: {s.archetype}")

    if s.recommendation:
        parts.append(f"recommendation: {s.recommendation}")

    if s.key_findings:
        parts.append("key findings: " + "; ".join(s.key_findings[:3]))

    if s.quality_mode and s.quality_mode != "normal":
        parts.append(f"(quality: {s.quality_mode})")

    return ". ".join(parts)
