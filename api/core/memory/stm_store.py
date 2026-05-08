"""Short-Term Memory Store — dual backend (SQLite + PostgreSQL).

Manages conversation sessions and turns within a session.
Both backends implement the same ConversationMemoryStore Protocol.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from api.core.harness import utc_now_iso
from api.core.memory.models import (
    ConversationSession,
    ConversationSessionStatus,
    TurnRecord,
    TurnSummary,
)
from api.core.settings import get_settings

# Optional PostgreSQL imports
try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


# -- Protocol --


class ConversationMemoryStore(Protocol):
    """Interface for short-term memory backends."""

    async def ensure_session(self, user_id: str) -> str:
        """Get or create an active session for the user, return session_id."""
        ...

    async def end_session(self, session_id: str) -> None:
        """Mark a session as completed."""
        ...

    async def save_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        run_id: str,
        query: str,
        summary: TurnSummary,
        artifacts: dict[str, Any] | None = None,
    ) -> int:
        """Persist a turn and return its turn_id."""
        ...

    async def load_turns(
        self,
        user_id: str,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[TurnRecord]:
        """Load recent turns for a user, optionally scoped to a session."""
        ...

    async def load_latest_summary(self, user_id: str) -> TurnSummary | None:
        """Load the most recent turn summary for a user."""
        ...

    async def load_session(self, session_id: str) -> ConversationSession | None:
        """Load session metadata."""
        ...


# -- SQLite Backend --


@dataclass
class SqliteConversationMemoryStore:
    """SQLite-backed short-term memory store. Suitable for local development."""

    db_path: str

    def __post_init__(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        import sqlite3

        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    turn_count INTEGER NOT NULL DEFAULT 0,
                    summary TEXT NOT NULL DEFAULT '',
                    key_topics TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'active'
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user
                    ON conversation_sessions(user_id, status);

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL
                        REFERENCES conversation_sessions(session_id)
                        ON DELETE CASCADE,
                    run_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    artifacts_json TEXT NOT NULL DEFAULT '{}',
                    memory_tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_turns_user
                    ON conversation_turns(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_turns_session
                    ON conversation_turns(session_id);
                """
            )

    async def ensure_session(self, user_id: str) -> str:
        clean = _clean_user_id(user_id)
        now = utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_id FROM conversation_sessions "
                "WHERE user_id = ? AND status = 'active' "
                "ORDER BY started_at DESC LIMIT 1",
                (clean,),
            ).fetchone()
            if row:
                return str(row[0])
            sid = f"sess-{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO conversation_sessions "
                "(session_id, user_id, started_at, status) VALUES (?, ?, ?, 'active')",
                (sid, clean, now),
            )
            return sid

    async def end_session(self, session_id: str) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversation_sessions SET status = 'completed', ended_at = ? "
                "WHERE session_id = ?",
                (now, session_id),
            )

    async def save_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        run_id: str,
        query: str,
        summary: TurnSummary,
        artifacts: dict[str, Any] | None = None,
    ) -> int:
        import json

        clean = _clean_user_id(user_id)
        now = utc_now_iso()
        summary_json = summary.model_dump_json()
        artifacts_json = json.dumps(artifacts or {}, ensure_ascii=False)
        tags_json = json.dumps(summary.tags, ensure_ascii=False)

        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO conversation_turns "
                "(user_id, session_id, run_id, query, summary_json, "
                "artifacts_json, memory_tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (clean, session_id, run_id, query, summary_json,
                 artifacts_json, tags_json, now),
            )
            turn_id = cur.lastrowid
            # update session turn_count + key_topics
            conn.execute(
                "UPDATE conversation_sessions SET turn_count = turn_count + 1 "
                "WHERE session_id = ?",
                (session_id,),
            )
            # merge key_topics
            existing_row = conn.execute(
                "SELECT key_topics FROM conversation_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if existing_row:
                existing_topics = json.loads(existing_row[0] or "[]")
                if isinstance(existing_topics, list):
                    merged = list(dict.fromkeys(existing_topics + summary.tags[:5]))
                    conn.execute(
                        "UPDATE conversation_sessions SET key_topics = ? "
                        "WHERE session_id = ?",
                        (json.dumps(merged, ensure_ascii=False), session_id),
                    )
            return int(turn_id or 0)

    async def load_turns(
        self,
        user_id: str,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[TurnRecord]:
        import json

        clean = _clean_user_id(user_id)
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT id, user_id, session_id, run_id, query, "
                    "summary_json, artifacts_json, memory_tags, created_at "
                    "FROM conversation_turns "
                    "WHERE user_id = ? AND session_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (clean, session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, user_id, session_id, run_id, query, "
                    "summary_json, artifacts_json, memory_tags, created_at "
                    "FROM conversation_turns "
                    "WHERE user_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (clean, limit),
                ).fetchall()

        results: list[TurnRecord] = []
        for row in rows:
            summary = TurnSummary.model_validate_json(row["summary_json"])
            results.append(TurnRecord(
                turn_id=row["id"],
                user_id=row["user_id"],
                session_id=row["session_id"],
                run_id=row["run_id"],
                query=row["query"],
                summary=summary,
                artifacts_json=json.loads(row["artifacts_json"] or "{}"),
                memory_tags=json.loads(row["memory_tags"] or "[]"),
                created_at=row["created_at"],
            ))
        return results

    async def load_latest_summary(self, user_id: str) -> TurnSummary | None:
        clean = _clean_user_id(user_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary_json FROM conversation_turns "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (clean,),
            ).fetchone()
        if row is None:
            return None
        return TurnSummary.model_validate_json(row["summary_json"])

    async def load_session(self, session_id: str) -> ConversationSession | None:
        import json

        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_id, user_id, started_at, ended_at, "
                "turn_count, summary, key_topics, status "
                "FROM conversation_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        key_topics = json.loads(row["key_topics"] or "[]")
        if not isinstance(key_topics, list):
            key_topics = []
        return ConversationSession(
            session_id=row["session_id"],
            user_id=row["user_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            turn_count=row["turn_count"],
            summary=row["summary"],
            key_topics=key_topics,
            status=ConversationSessionStatus(row["status"]),
        )


# -- PostgreSQL Backend --


@dataclass
class PgConversationMemoryStore:
    """PostgreSQL-backed short-term memory store. Suitable for production."""

    database_url: str

    def __post_init__(self) -> None:
        self._initialize()

    def _connect(self):
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        return psycopg.connect(self.database_url)

    def _initialize(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        ended_at TIMESTAMPTZ,
                        turn_count INTEGER NOT NULL DEFAULT 0,
                        summary TEXT NOT NULL DEFAULT '',
                        key_topics TEXT[] NOT NULL DEFAULT '{}',
                        status TEXT NOT NULL DEFAULT 'active'
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_user "
                    "ON conversation_sessions(user_id, status)"
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL
                            REFERENCES conversation_sessions(session_id)
                            ON DELETE CASCADE,
                        run_id TEXT NOT NULL,
                        query TEXT NOT NULL,
                        summary_json JSONB NOT NULL DEFAULT '{}',
                        artifacts_json JSONB NOT NULL DEFAULT '{}',
                        memory_tags TEXT[] NOT NULL DEFAULT '{}',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_turns_user "
                    "ON conversation_turns(user_id, created_at DESC)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_turns_session "
                    "ON conversation_turns(session_id)"
                )

    async def ensure_session(self, user_id: str) -> str:
        clean = _clean_user_id(user_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id FROM conversation_sessions "
                    "WHERE user_id = %s AND status = 'active' "
                    "ORDER BY started_at DESC LIMIT 1",
                    (clean,),
                )
                row = cur.fetchone()
                if row:
                    return str(row[0])
                sid = f"sess-{uuid.uuid4().hex[:12]}"
                cur.execute(
                    "INSERT INTO conversation_sessions "
                    "(session_id, user_id, status) VALUES (%s, %s, 'active')",
                    (sid, clean),
                )
                return sid

    async def end_session(self, session_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversation_sessions SET status = 'completed', "
                    "ended_at = now() WHERE session_id = %s",
                    (session_id,),
                )

    async def save_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        run_id: str,
        query: str,
        summary: TurnSummary,
        artifacts: dict[str, Any] | None = None,
    ) -> int:
        import json

        clean = _clean_user_id(user_id)
        summary_json = summary.model_dump_json()
        artifacts_json = json.dumps(artifacts or {}, ensure_ascii=False)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversation_turns "
                    "(user_id, session_id, run_id, query, summary_json, "
                    "artifacts_json, memory_tags) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "RETURNING id",
                    (clean, session_id, run_id, query, summary_json,
                     artifacts_json, summary.tags),
                )
                turn_id_row = cur.fetchone()
                turn_id = int(turn_id_row[0]) if turn_id_row else 0
                cur.execute(
                    "UPDATE conversation_sessions SET turn_count = turn_count + 1 "
                    "WHERE session_id = %s",
                    (session_id,),
                )
                cur.execute(
                    "UPDATE conversation_sessions SET key_topics = ("
                    "  SELECT array_agg(DISTINCT t) FROM ("
                    "    SELECT unnest(key_topics) AS t "
                    "    UNION ALL "
                    "    SELECT unnest(%s::text[]) AS t"
                    "  ) sub"
                    ") WHERE session_id = %s",
                    (summary.tags[:5], session_id),
                )
                return turn_id

    async def load_turns(
        self,
        user_id: str,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[TurnRecord]:
        clean = _clean_user_id(user_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                if session_id:
                    cur.execute(
                        "SELECT id, user_id, session_id, run_id, query, "
                        "summary_json, artifacts_json, memory_tags, created_at "
                        "FROM conversation_turns "
                        "WHERE user_id = %s AND session_id = %s "
                        "ORDER BY created_at DESC LIMIT %s",
                        (clean, session_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT id, user_id, session_id, run_id, query, "
                        "summary_json, artifacts_json, memory_tags, created_at "
                        "FROM conversation_turns "
                        "WHERE user_id = %s "
                        "ORDER BY created_at DESC LIMIT %s",
                        (clean, limit),
                    )
                rows = cur.fetchall()

        results: list[TurnRecord] = []
        for row in rows:
            (tid, uid, sid, rid, q, summary_json, artifacts_json,
             memory_tags, created_at) = row
            summary = TurnSummary.model_validate_json(str(summary_json) if isinstance(summary_json, str) else summary_json)
            artifacts = artifacts_json if isinstance(artifacts_json, dict) else {}
            tags = list(memory_tags) if isinstance(memory_tags, list) else []
            created = str(created_at) if created_at else ""
            results.append(TurnRecord(
                turn_id=tid,
                user_id=uid,
                session_id=sid,
                run_id=rid,
                query=q,
                summary=summary,
                artifacts_json=artifacts,
                memory_tags=tags,
                created_at=created,
            ))
        return results

    async def load_latest_summary(self, user_id: str) -> TurnSummary | None:
        clean = _clean_user_id(user_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT summary_json FROM conversation_turns "
                    "WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                    (clean,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        raw = row[0]
        if isinstance(raw, str):
            return TurnSummary.model_validate_json(raw)
        return TurnSummary.model_validate(raw)

    async def load_session(self, session_id: str) -> ConversationSession | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, user_id, started_at, ended_at, "
                    "turn_count, summary, key_topics, status "
                    "FROM conversation_sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        (sid, uid, started_at, ended_at, turn_count,
         summary, key_topics, status) = row
        topics = list(key_topics) if isinstance(key_topics, list) else []
        return ConversationSession(
            session_id=str(sid),
            user_id=str(uid),
            started_at=str(started_at) if started_at else "",
            ended_at=str(ended_at) if ended_at else None,
            turn_count=int(turn_count or 0),
            summary=str(summary or ""),
            key_topics=topics,
            status=ConversationSessionStatus(str(status)),
        )


# -- Helpers --


def _clean_user_id(user_id: str) -> str:
    return str(user_id or "").strip()


# -- Factory --


def build_conversation_memory_store() -> ConversationMemoryStore | None:
    """Build the appropriate STM backend based on settings."""
    settings = get_settings()
    if not settings.enable_conversation_memory:
        return None
    # Prefer PostgreSQL if RAG_DATABASE_URL is set (reuse existing DB)
    database_url = str(settings.rag_database_url or "").strip()
    if database_url:
        return PgConversationMemoryStore(database_url)
    # Fall back to SQLite
    db_path = str(settings.cache_db_path or "var/cache/conversation_memory.sqlite")
    return SqliteConversationMemoryStore(db_path)


async def load_memory_for_user(
    *,
    store: ConversationMemoryStore | None,
    user_id: str,
) -> tuple[str | None, TurnSummary | None]:
    """Load the most recent session_id and summary for a user.

    Returns (session_id, TurnSummary) or (None, None).
    """
    clean = _clean_user_id(user_id)
    if not clean or store is None:
        return None, None
    try:
        summary = await store.load_latest_summary(clean)
        session_id = await store.ensure_session(clean)
        return session_id, summary
    except Exception:
        return None, None


async def save_memory_turn(
    *,
    store: ConversationMemoryStore | None,
    user_id: str,
    session_id: str,
    run_id: str,
    query: str,
    summary: TurnSummary,
    artifacts: dict[str, Any] | None = None,
) -> int | None:
    """Save a turn to the memory store. Returns turn_id or None on failure."""
    clean = _clean_user_id(user_id)
    if not clean or store is None:
        return None
    try:
        return await store.save_turn(
            user_id=clean,
            session_id=session_id,
            run_id=run_id,
            query=query,
            summary=summary,
            artifacts=artifacts,
        )
    except Exception:
        return None
