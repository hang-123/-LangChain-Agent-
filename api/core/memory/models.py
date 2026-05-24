"""Memory data models for the bettafish_langchain memory system."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# -- Enums --


class MemoryType(str, Enum):
    """Classification of long-term memories by cognitive type (v2.0).

    Types are split by 4 axes: decay speed, retrieval method, injection target, update frequency.
    A type deserves its own class when it differs on >=2 axes from existing types.
    """

    ENTITY_KNOWLEDGE = "entity_knowledge"  # Verifiable facts about specific companies/roles
    PATTERN = "pattern"                    # User characteristics extracted from behavior
    PREFERENCE = "preference"              # Explicit/implicit user preferences
    SEMANTIC = "semantic"                  # Industry general knowledge, interview methodology
    EPISODIC = "episodic"                  # Single research run record and conclusion

    # Lifetime overrides per type (days; None = never expires)
    @property
    def lifetime_days(self) -> int | None:
        _LIFETIME = {
            MemoryType.ENTITY_KNOWLEDGE: 180,
            MemoryType.PATTERN: 180,
            MemoryType.PREFERENCE: None,
            MemoryType.SEMANTIC: 120,
            MemoryType.EPISODIC: 60,
        }
        return _LIFETIME.get(self)

    # Whether this type supports stale-while-revalidate refresh
    @property
    def supports_refresh(self) -> bool:
        return self in (MemoryType.ENTITY_KNOWLEDGE, MemoryType.SEMANTIC)


class MemoryStatus(str, Enum):
    """Lifecycle status of a memory record (v2.0)."""

    ACTIVE = "active"
    EXPIRED_PENDING_REFRESH = "expired_pending_refresh"
    REFRESH_FAILED = "refresh_failed"
    SOFT_DELETED = "soft_deleted"


class SourceType(str, Enum):
    """Origin of a memory record."""

    EVALUATION_REPORT = "evaluation_report"
    INTERVIEW_EXP = "interview_exp"
    USER_FEEDBACK = "user_feedback"
    USER_PREFERENCE = "user_preference"
    STRATEGY_EVOLUTION = "strategy_evolution"
    SYSTEM_OBSERVATION = "system_observation"
    RAG_WRITEBACK = "rag_writeback"  # v2.0: RAG → LTM bridge


class ConversationSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


# -- Short-Term Memory Models --


class TurnSummary(BaseModel):
    """Structured summary of a single agent interaction turn."""

    query: str = ""
    company: str = ""
    role: str = ""
    archetype: str | None = None
    overall_score: float | None = None
    recommendation: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    quality_mode: str = "normal"


class TurnRecord(BaseModel):
    """A persisted turn in the conversation history."""

    turn_id: int | None = None
    user_id: str
    session_id: str
    run_id: str
    query: str
    summary: TurnSummary
    artifacts_json: dict[str, Any] = Field(default_factory=dict)
    memory_tags: list[str] = Field(default_factory=list)
    created_at: str = ""


class ConversationSession(BaseModel):
    """Metadata for a multi-turn conversation session."""

    session_id: str
    user_id: str
    started_at: str = ""
    ended_at: str | None = None
    turn_count: int = 0
    summary: str = ""
    key_topics: list[str] = Field(default_factory=list)
    status: ConversationSessionStatus = ConversationSessionStatus.ACTIVE


# -- Long-Term Memory Models --


class LongTermMemory(BaseModel):
    """A persistent memory record that spans sessions (v2.0).

    v2.0 additions: lifetime_days, status, content_hash, refresh_attempts, last_refreshed_at.
    Decay is now time-driven: importance = initial_importance × max(0, 1 - days_elapsed / lifetime_days).
    """

    memory_id: str
    user_id: str
    memory_type: MemoryType
    source_type: SourceType
    content: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    initial_importance: float = Field(default=0.5, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    lifetime_days: int | None = None
    access_count: int = 0
    status: MemoryStatus = MemoryStatus.ACTIVE
    content_hash: str | None = None
    refresh_attempts: int = 0
    last_accessed_at: str | None = None
    last_refreshed_at: str | None = None
    created_at: str = ""
    expires_at: str | None = None


class MemoryEmbedding(BaseModel):
    """Vector embedding of a memory chunk for semantic search."""

    memory_id: str
    user_id: str
    chunk_text: str
    source_type: SourceType
    created_at: str = ""


# -- Retrieval Models --


class MemoryHit(BaseModel):
    """A retrieved memory with relevance score."""

    memory: LongTermMemory
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_method: Literal["vector", "keyword", "hybrid"] = "hybrid"


class MemoryContext(BaseModel):
    """Formatted memory context ready for injection into agent state (v2.0).

    Hits are grouped by type for distributed injection:
      - entity_knowledge → SearchAgent query expansion
      - pattern → Supervisor routing
      - preference → Supervisor + Gate
      - semantic → AnalysisAgent / ReportAgent
      - episodic → MemoryRetrievalNode context block
    """

    hits: list[MemoryHit] = Field(default_factory=list)
    formatted_text: str = ""
    hit_count: int = 0
    retrieval_time_ms: float = 0.0
    # v2.0: typed groupings for distributed injection
    entity_hits: list[MemoryHit] = Field(default_factory=list)
    pattern_hits: list[MemoryHit] = Field(default_factory=list)
    preference_hits: list[MemoryHit] = Field(default_factory=list)
    semantic_hits: list[MemoryHit] = Field(default_factory=list)
    episodic_hits: list[MemoryHit] = Field(default_factory=list)


# -- Utility Functions --


def build_memory_tags(
    *,
    company: str = "",
    role: str = "",
    archetype: str | None = None,
    score: float | None = None,
    recommendation: str | None = None,
) -> list[str]:
    """Build structured tags from turn metadata for filtered retrieval."""
    tags: list[str] = []
    if company:
        tags.append(f"company:{company.lower().strip()}")
    if role:
        tags.append(f"role:{role.lower().strip()}")
    if archetype:
        tags.append(f"archetype:{archetype.lower().strip()}")
    if score is not None:
        bucket = "high" if score >= 4.0 else "medium" if score >= 3.0 else "low"
        tags.append(f"score:{bucket}")
    if recommendation:
        tags.append(f"rec:{recommendation.lower().strip()}")
    return tags


def extract_keywords(text: str, min_length: int = 3) -> list[str]:
    """Extract meaningful keywords from a text for structured filtering.

    Strips common stopwords and short tokens.
    """
    STOPWORDS: set[str] = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "in", "on", "at", "to", "for", "of", "with", "from", "by",
        "and", "or", "not", "but", "if", "then", "else", "when",
        "this", "that", "it", "its", "we", "you", "they", "he", "she",
        "role", "position", "team", "work", "job", "candidate",
    }
    words = text.lower().replace("/", " ").replace("-", " ").split()
    return [
        w for w in words
        if len(w) >= min_length and w not in STOPWORDS
    ]
