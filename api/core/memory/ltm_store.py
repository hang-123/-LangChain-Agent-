"""Long-Term Memory Store — PostgreSQL + pgvector backend.

PostgreSQL is required for both structured metadata and vector embeddings.
SQLite branch removed in v2.0.
"""

from __future__ import annotations

import json
import uuid
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

    async def save(self, memory: LongTermMemory) -> str: ...
    async def get(self, memory_id: str) -> LongTermMemory | None: ...
    async def search_by_user(
        self, user_id: str, *, memory_type: MemoryType | None = None,
        source_type: SourceType | None = None, min_importance: float = 0.0,
        limit: int = 50,
    ) -> list[LongTermMemory]: ...
    async def update_access(self, memory_id: str) -> None: ...
    async def delete(self, memory_id: str) -> bool: ...
    async def apply_decay(self, user_id: str, decay_factor: float = 0.9) -> int: ...
    async def expire(self, user_id: str) -> int: ...
    async def count_by_user(self, user_id: str) -> int: ...


# -- PostgreSQL Backend --


class PostgresLongTermMemoryStore:
    """PostgreSQL + pgvector backed long-term memory store."""

    def __init__(self, database_url: str, *, embedding_dim: int = 1024) -> None:
        self.database_url = database_url
        self.embedding_dim = embedding_dim
        self._initialize()

    def _connect(self):
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        conn = psycopg.connect(self.database_url)
        if register_vector is not None:
            register_vector(conn)
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS long_term_memories (
                        memory_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        memory_type TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        structured_data JSONB NOT NULL DEFAULT '{}',
                        importance REAL NOT NULL DEFAULT 0.5,
                        access_count INTEGER NOT NULL DEFAULT 0,
                        last_accessed_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        expires_at TIMESTAMPTZ
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ltm_user_type "
                    "ON long_term_memories(user_id, memory_type)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ltm_importance "
                    "ON long_term_memories(user_id, importance DESC)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ltm_expires "
                    "ON long_term_memories(expires_at) WHERE expires_at IS NOT NULL"
                )
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS memory_embeddings (
                        memory_id TEXT PRIMARY KEY
                            REFERENCES long_term_memories(memory_id) ON DELETE CASCADE,
                        user_id TEXT NOT NULL,
                        chunk_text TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        embedding vector({int(self.embedding_dim)}) NOT NULL,
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

    # -- CRUD --

    async def save(self, memory: LongTermMemory) -> str:
        memory_id = memory.memory_id or f"mem-{uuid.uuid4().hex[:16]}"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO long_term_memories
                    (memory_id, user_id, memory_type, source_type, content,
                     structured_data, importance, access_count,
                     last_accessed_at, created_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (memory_id) DO UPDATE SET
                        user_id = excluded.user_id,
                        memory_type = excluded.memory_type,
                        source_type = excluded.source_type,
                        content = excluded.content,
                        structured_data = excluded.structured_data,
                        importance = excluded.importance,
                        access_count = excluded.access_count,
                        last_accessed_at = excluded.last_accessed_at,
                        expires_at = excluded.expires_at""",
                    (
                        memory_id, memory.user_id, memory.memory_type.value,
                        memory.source_type.value, memory.content,
                        json.dumps(memory.structured_data, ensure_ascii=False),
                        memory.importance, memory.access_count,
                        memory.last_accessed_at or utc_now_iso(),
                        memory.created_at or utc_now_iso(),
                        memory.expires_at,
                    ),
                )
        # Store embedding (fire-and-forget)
        if memory.content.strip():
            import asyncio as _asyncio
            try:
                loop = _asyncio.get_running_loop()
                loop.create_task(
                    self.upsert_memory_embedding(
                        memory_id=memory_id, user_id=memory.user_id,
                        chunk_text=memory.content[:2000],
                        source_type=memory.source_type.value,
                    )
                )
            except RuntimeError:
                pass
        return memory_id

    async def get(self, memory_id: str) -> LongTermMemory | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM long_term_memories WHERE memory_id = %s",
                    (memory_id,),
                )
                row = cur.fetchone()
        return self._row_to_memory(row) if row else None

    async def search_by_user(
        self, user_id: str, *, memory_type: MemoryType | None = None,
        source_type: SourceType | None = None, min_importance: float = 0.0,
        limit: int = 50,
    ) -> list[LongTermMemory]:
        query = "SELECT * FROM long_term_memories WHERE user_id = %s"
        params: list[Any] = [user_id]

        if memory_type is not None:
            query += " AND memory_type = %s"
            params.append(memory_type.value)
        if source_type is not None:
            query += " AND source_type = %s"
            params.append(source_type.value)
        if min_importance > 0:
            query += " AND importance >= %s"
            params.append(min_importance)

        query += " ORDER BY importance DESC, created_at DESC LIMIT %s"
        params.append(limit)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [m for row in rows if (m := self._row_to_memory(row)) is not None]

    async def update_access(self, memory_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE long_term_memories SET access_count = access_count + 1, "
                    "last_accessed_at = now() WHERE memory_id = %s",
                    (memory_id,),
                )

    async def delete(self, memory_id: str) -> bool:
        now = utc_now_iso()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE long_term_memories SET importance = 0.0, "
                    "expires_at = %s, last_accessed_at = %s WHERE memory_id = %s",
                    (now, now, memory_id),
                )
                return cur.rowcount > 0

    async def count_by_user(self, user_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM long_term_memories WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
        return int(row[0]) if row else 0

    # -- Decay & Expiry --

    async def apply_decay(self, user_id: str, decay_factor: float = 0.9) -> int:
        """Apply multiplicative decay to unaccessed memories, boost frequent ones."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                # Decay unaccessed
                cur.execute(
                    "UPDATE long_term_memories "
                    "SET importance = GREATEST(0.0, importance * %s) "
                    "WHERE user_id = %s AND access_count = 0 AND importance > 0.01",
                    (decay_factor, user_id),
                )
                decayed = cur.rowcount
                # Boost frequently accessed
                cur.execute(
                    "UPDATE long_term_memories "
                    "SET importance = LEAST(1.0, importance * 1.1) "
                    "WHERE user_id = %s AND access_count >= 3",
                    (user_id,),
                )
        return decayed

    async def expire(self, user_id: str) -> int:
        """Remove memories past their expires_at or with importance < 0.1."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM long_term_memories "
                    "WHERE user_id = %s AND importance < 0.1 "
                    "AND expires_at IS NOT NULL AND expires_at < now()",
                    (user_id,),
                )
        return cur.rowcount

    # -- pgvector --

    async def search_by_vector(
        self, query: str, user_id: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        from api.core.llm import embed_query

        embedding = await embed_query(query)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT me.memory_id, me.user_id, me.chunk_text, me.source_type,
                           1 - (me.embedding <=> %s::vector) AS score
                    FROM memory_embeddings me
                    WHERE me.user_id = %s
                    ORDER BY me.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, user_id, embedding, int(top_k)),
                )
                rows = cur.fetchall()
        return [
            {
                "memory_id": row[0], "user_id": row[1],
                "chunk_text": row[2], "source_type": row[3],
                "score": float(row[4] or 0.0),
            }
            for row in rows
        ]

    async def upsert_memory_embedding(
        self, memory_id: str, user_id: str, chunk_text: str, source_type: str
    ) -> bool:
        from api.core.llm import embed_query

        try:
            embedding = await embed_query(chunk_text)
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO memory_embeddings
                        (memory_id, user_id, chunk_text, source_type, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (memory_id) DO UPDATE SET
                            chunk_text = excluded.chunk_text,
                            embedding = excluded.embedding""",
                        (memory_id, user_id, chunk_text, source_type, embedding),
                    )
            return True
        except Exception:
            return False

    def _row_to_memory(self, row: Any) -> LongTermMemory | None:
        if row is None:
            return None
        try:
            importance = row["importance"] if hasattr(row, "__getitem__") else row[6]
            access_count = row["access_count"] if hasattr(row, "__getitem__") else row[7]
            return LongTermMemory(
                memory_id=str(row[0]),
                user_id=str(row[1]),
                memory_type=MemoryType(str(row[2])),
                source_type=SourceType(str(row[3])),
                content=str(row[4]),
                structured_data=(
                    row[5] if isinstance(row[5], dict)
                    else json.loads(str(row[5] or "{}"))
                ),
                importance=float(0.5 if importance is None else importance),
                access_count=int(0 if access_count is None else access_count),
                last_accessed_at=str(row[8] or "") if len(row) > 8 else "",
                created_at=str(row[9] or "") if len(row) > 9 else "",
                expires_at=str(row[10]) if len(row) > 10 and row[10] else None,
            )
        except (ValueError, TypeError, KeyError):
            return None


# -- Factory --


def build_ltm_store() -> LongTermMemoryStore | None:
    """Build the LTM store. Requires PostgreSQL + pgvector."""
    settings = get_settings()
    if not settings.enable_ltm:
        return None
    database_url = str(
        settings.ltm_database_url or settings.rag_database_url or ""
    ).strip()
    if not database_url:
        raise RuntimeError(
            "PostgreSQL connection URL is required when ENABLE_LTM is True. "
            "Set RAG_DATABASE_URL or LTM_DATABASE_URL."
        )
    return PostgresLongTermMemoryStore(
        database_url, embedding_dim=int(settings.embedding_dim or 1024)
    )
