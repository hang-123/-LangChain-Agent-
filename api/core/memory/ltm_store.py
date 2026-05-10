"""Long-Term Memory Store — cross-session persistent memory.

Uses SQLite for structured metadata + optionally pgvector for embeddings.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from api.core.harness import utc_now_iso
from api.core.memory.models import (
    LongTermMemory,
    MemoryEmbedding,
    MemoryType,
    SourceType,
)
from api.core.settings import get_settings

try:
    import psycopg
    from pgvector.psycopg import register_vector
except Exception:
    psycopg = None  # type: ignore
    register_vector = None  # type: ignore


# -- Protocol --


class LongTermMemoryStore(Protocol):
    """Interface for long-term memory backends."""

    async def save(self, memory: LongTermMemory) -> str:
        """Store a memory. Returns memory_id."""
        ...

    async def get(self, memory_id: str) -> LongTermMemory | None:
        """Retrieve a single memory by ID."""
        ...

    async def search_by_user(
        self,
        user_id: str,
        *,
        memory_type: MemoryType | None = None,
        source_type: SourceType | None = None,
        min_importance: float = 0.0,
        limit: int = 50,
    ) -> list[LongTermMemory]:
        """Structured search with filters."""
        ...

    async def update_access(self, memory_id: str) -> None:
        """Increment access_count and update last_accessed_at."""
        ...

    async def delete(self, memory_id: str) -> bool:
        """Soft-delete by setting importance to 0 and expiring. Returns True if found."""
        ...

    async def apply_decay(self, user_id: str, decay_factor: float = 0.9) -> int:
        """Reduce importance of memories below threshold. Returns count of decayed."""
        ...

    async def expire(self, user_id: str) -> int:
        """Remove memories past their expires_at. Returns count of removed."""
        ...

    async def count_by_user(self, user_id: str) -> int:
        """Count total memories for a user."""
        ...


# -- SQLite Backend --


class SqliteLongTermMemoryStore:
    """SQLite-backed long-term memory store."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        import sqlite3

        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _managed_connection(self):
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._managed_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    memory_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    structured_data TEXT NOT NULL DEFAULT '{}',
                    importance REAL NOT NULL DEFAULT 0.5,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed_at TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ltm_user_type
                    ON long_term_memories(user_id, memory_type);
                CREATE INDEX IF NOT EXISTS idx_ltm_importance
                    ON long_term_memories(user_id, importance DESC);
                CREATE INDEX IF NOT EXISTS idx_ltm_expires
                    ON long_term_memories(expires_at) WHERE expires_at IS NOT NULL;

                CREATE TABLE IF NOT EXISTS memory_embeddings_sqlite (
                    memory_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (memory_id) REFERENCES long_term_memories(memory_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_mem_emb_user
                    ON memory_embeddings_sqlite(user_id);
                """
            )

    async def save(self, memory: LongTermMemory) -> str:
        now = utc_now_iso()
        memory_id = memory.memory_id or f"mem-{uuid.uuid4().hex[:16]}"
        with self._managed_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO long_term_memories "
                "(memory_id, user_id, memory_type, source_type, content, "
                "structured_data, importance, access_count, "
                "last_accessed_at, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    memory_id,
                    memory.user_id,
                    memory.memory_type.value,
                    memory.source_type.value,
                    memory.content,
                    json.dumps(memory.structured_data, ensure_ascii=False),
                    memory.importance,
                    memory.access_count,
                    memory.last_accessed_at or now,
                    memory.created_at or now,
                    memory.expires_at,
                ),
            )
        # Try to store embedding for pgvector semantic search (fire-and-forget)
        if memory.content.strip():
            import asyncio as _asyncio
            try:
                loop = _asyncio.get_running_loop()
                loop.create_task(
                    self.upsert_memory_embedding(
                        memory_id=memory_id,
                        user_id=memory.user_id,
                        chunk_text=memory.content[:2000],
                        source_type=memory.source_type.value,
                    )
                )
            except RuntimeError:
                pass
        return memory_id

    async def get(self, memory_id: str) -> LongTermMemory | None:
        with self._managed_connection() as conn:
            row = conn.execute(
                "SELECT * FROM long_term_memories WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
        return self._row_to_memory(row) if row else None

    async def search_by_user(
        self,
        user_id: str,
        *,
        memory_type: MemoryType | None = None,
        source_type: SourceType | None = None,
        min_importance: float = 0.0,
        limit: int = 50,
    ) -> list[LongTermMemory]:
        query = "SELECT * FROM long_term_memories WHERE user_id = ?"
        params: list[Any] = [user_id]

        if memory_type is not None:
            query += " AND memory_type = ?"
            params.append(memory_type.value)
        if source_type is not None:
            query += " AND source_type = ?"
            params.append(source_type.value)
        if min_importance > 0:
            query += " AND importance >= ?"
            params.append(min_importance)

        query += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)

        with self._managed_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [m for row in rows if (m := self._row_to_memory(row)) is not None]

    async def update_access(self, memory_id: str) -> None:
        now = utc_now_iso()
        with self._managed_connection() as conn:
            conn.execute(
                "UPDATE long_term_memories SET access_count = access_count + 1, "
                "last_accessed_at = ? WHERE memory_id = ?",
                (now, memory_id),
            )

    async def delete(self, memory_id: str) -> bool:
        now = utc_now_iso()
        with self._managed_connection() as conn:
            cur = conn.execute(
                "UPDATE long_term_memories SET importance = 0.0, "
                "expires_at = ?, last_accessed_at = ? WHERE memory_id = ?",
                (now, now, memory_id),
            )
            return cur.rowcount > 0

    async def apply_decay(self, user_id: str, decay_factor: float = 0.9) -> int:
        """Reduce importance for low-access memories.

        For memories with access_count == 0: importance *= decay_factor.
        For frequently accessed memories: importance = min(1.0, importance * 1.1).
        """
        with self._managed_connection() as conn:
            # Decay unaccessed memories
            cur = conn.execute(
                "UPDATE long_term_memories "
                "SET importance = MAX(0.0, importance * ?) "
                "WHERE user_id = ? AND access_count = 0 AND importance > 0.01",
                (decay_factor, user_id),
            )
            decayed = cur.rowcount
            # Boost frequently accessed memories
            conn.execute(
                "UPDATE long_term_memories "
                "SET importance = MIN(1.0, importance * 1.1) "
                "WHERE user_id = ? AND access_count >= 3",
                (user_id,),
            )
        return decayed

    async def expire(self, user_id: str) -> int:
        """Remove memories past expires_at or with importance < 0.1."""
        with self._managed_connection() as conn:
            cur = conn.execute(
                "DELETE FROM long_term_memories "
                "WHERE user_id = ? AND importance < 0.1 "
                "AND (expires_at IS NOT NULL AND expires_at < ?)",
                (user_id, utc_now_iso()),
            )
        return cur.rowcount

    async def count_by_user(self, user_id: str) -> int:
        with self._managed_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM long_term_memories WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    async def save_embedding(self, emb: MemoryEmbedding) -> None:
        """Store embedding metadata (SQLite-only, no vector index)."""
        now = utc_now_iso()
        with self._managed_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_embeddings_sqlite "
                "(memory_id, user_id, chunk_text, source_type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    emb.memory_id,
                    emb.user_id,
                    emb.chunk_text,
                    emb.source_type.value,
                    emb.created_at or now,
                ),
            )

    # -- pgvector support (optional, gracefully degrades if not configured) --

    def _pg_connect(self):
        """Connect to pgvector for LTM semantic search."""
        from api.core.settings import get_settings
        settings = get_settings()
        url = str(settings.ltm_database_url or "").strip()
        if not url or psycopg is None:
            return None
        conn = psycopg.connect(url)
        if register_vector is not None:
            register_vector(conn)
        return conn

    def _ensure_pgvector_table(self) -> bool:
        """Create pgvector memory_embeddings table if not exists."""
        conn = self._pg_connect()
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory_embeddings (
                        memory_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        chunk_text TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        embedding vector(1536) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_embeddings_user "
                    "ON memory_embeddings(user_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_embeddings_vector "
                    "ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)"
                )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    async def search_by_vector(
        self, query: str, user_id: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Vector semantic search over memory embeddings using pgvector."""
        from api.core.llm import embed_query

        conn = self._pg_connect()
        if conn is None:
            return []

        try:
            embedding = await embed_query(query)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT memory_id, user_id, chunk_text, source_type,
                           1 - (embedding <=> %s::vector) AS score
                    FROM memory_embeddings
                    WHERE user_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, user_id, embedding, int(top_k)),
                )
                rows = cur.fetchall()
            return [
                {
                    "memory_id": row[0],
                    "user_id": row[1],
                    "chunk_text": row[2],
                    "source_type": row[3],
                    "score": float(row[4] or 0.0),
                }
                for row in rows
            ]
        except Exception:
            return []
        finally:
            conn.close()

    async def upsert_memory_embedding(
        self, memory_id: str, user_id: str, chunk_text: str, source_type: str
    ) -> bool:
        """Store a memory embedding in pgvector."""
        from api.core.llm import embed_query

        if not self._ensure_pgvector_table():
            return False

        try:
            embedding = await embed_query(chunk_text)
            conn = self._pg_connect()
            if conn is None:
                return False
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO memory_embeddings (memory_id, user_id, chunk_text, source_type, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (memory_id) DO UPDATE SET
                            chunk_text = excluded.chunk_text,
                            embedding = excluded.embedding
                        """,
                        (memory_id, user_id, chunk_text, source_type, embedding),
                    )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception:
            return False

    def _row_to_memory(self, row: Any) -> LongTermMemory | None:
        if row is None:
            return None
        try:
            importance = row["importance"]
            access_count = row["access_count"]
            return LongTermMemory(
                memory_id=str(row["memory_id"]),
                user_id=str(row["user_id"]),
                memory_type=MemoryType(str(row["memory_type"])),
                source_type=SourceType(str(row["source_type"])),
                content=str(row["content"]),
                structured_data=json.loads(str(row["structured_data"] or "{}")),
                importance=float(0.5 if importance is None else importance),
                access_count=int(0 if access_count is None else access_count),
                last_accessed_at=str(row["last_accessed_at"] or ""),
                created_at=str(row["created_at"] or ""),
                expires_at=str(row["expires_at"]) if row["expires_at"] else None,
            )
        except (ValueError, TypeError, KeyError):
            return None


# -- Factory --


def build_ltm_store() -> LongTermMemoryStore | None:
    """Build the LTM store based on settings."""
    settings = get_settings()
    # LTM requires the STM to be enabled (depends on conversation tracking)
    if not settings.enable_conversation_memory:
        return None
    db_path = str(settings.cache_db_path or "var/cache/ltm.sqlite")
    # Use dedicated LTM path
    ltm_path = Path(db_path).parent / "long_term_memory.sqlite"
    return SqliteLongTermMemoryStore(str(ltm_path))
