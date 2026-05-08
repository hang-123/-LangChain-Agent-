"""Memory system for bettafish_langchain.

Layered architecture:
  Layer 1: Working Memory  — current session context in AgentState
  Layer 2: Short-Term Memory — multi-turn within a session (SQLite/PG)
  Layer 3: Long-Term Memory  — cross-session persistent (SQLite + pgvector)
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
    SqliteConversationMemoryStore,
    build_conversation_memory_store,
    load_memory_for_user,
    save_memory_turn,
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
    "SqliteConversationMemoryStore",
    "build_conversation_memory_store",
    "load_memory_for_user",
    "save_memory_turn",
]
