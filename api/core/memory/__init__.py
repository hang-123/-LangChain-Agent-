"""Memory system for bettafish_langchain.

Layered architecture:
  Layer 1: Working Memory  — current session context in AgentState
  Layer 2: Short-Term Memory — multi-turn within a session (PostgreSQL)
  Layer 3: Long-Term Memory  — cross-session persistent (PostgreSQL + pgvector)
"""

from api.core.memory.models import (
    ConversationSession,
    ConversationSessionStatus,
    LongTermMemory,
    MemoryHit,
    MemoryType,
    SourceType,
    TurnRecord,
    TurnSummary,
    build_memory_tags,
    extract_keywords,
)

from api.core.memory.stm_store import (
    ConversationMemoryStore,
    PostgresConversationMemoryStore,
    build_conversation_memory_store,
    load_memory_for_user,
    save_memory_turn,
)

from api.core.memory.ltm_store import (
    LongTermMemoryStore,
    PostgresLongTermMemoryStore,
    build_ltm_store,
)

__all__ = [
    # models
    "ConversationSession",
    "ConversationSessionStatus",
    "LongTermMemory",
    "MemoryHit",
    "MemoryType",
    "SourceType",
    "TurnRecord",
    "TurnSummary",
    "build_memory_tags",
    "extract_keywords",
    # stm_store
    "ConversationMemoryStore",
    "PostgresConversationMemoryStore",
    "build_conversation_memory_store",
    "load_memory_for_user",
    "save_memory_turn",
    # ltm_store
    "LongTermMemoryStore",
    "PostgresLongTermMemoryStore",
    "build_ltm_store",
]
