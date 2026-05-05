from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from typing import Any

try:
    import redis
except Exception:  # pragma: no cover
    redis = None  # type: ignore[assignment]


class SQLiteJsonCache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at
                ON cache_entries (expires_at)
                """
            )

    def _digest(self, namespace: str, key: str) -> str:
        raw = f"{namespace}:{key}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        digest = self._digest(namespace, key)
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload, expires_at
                FROM cache_entries
                WHERE namespace = ? AND cache_key = ?
                """,
                (namespace, digest),
            ).fetchone()
            if row is None:
                return None

            payload_text, expires_at = row
            if float(expires_at) <= now:
                connection.execute(
                    "DELETE FROM cache_entries WHERE namespace = ? AND cache_key = ?",
                    (namespace, digest),
                )
                return None

        payload = json.loads(str(payload_text))
        return payload if isinstance(payload, dict) else None

    def set(self, namespace: str, key: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return

        digest = self._digest(namespace, key)
        now = time.time()
        expires_at = now + ttl_seconds
        payload_text = json.dumps(payload, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries (namespace, cache_key, payload, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (namespace, digest, payload_text, now, expires_at),
            )


def normalize_redis_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        scheme = "rediss" if parsed.scheme == "https" else "redis"
        path = parsed.path or "/0"
        if path == "/":
            path = "/0"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))
    return raw


class RedisJsonCache:
    def __init__(self, redis_url: str) -> None:
        if redis is None:
            raise RuntimeError("redis package is not installed")
        self.redis_url = normalize_redis_url(redis_url)
        self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)

    def _digest(self, namespace: str, key: str) -> str:
        raw = f"{namespace}:{key}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _redis_key(self, namespace: str, key: str) -> str:
        return f"bettafish:cache:{namespace}:{self._digest(namespace, key)}"

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        payload_text = self.client.get(self._redis_key(namespace, key))
        if not payload_text:
            return None
        payload = json.loads(str(payload_text))
        return payload if isinstance(payload, dict) else None

    def set(self, namespace: str, key: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        self.client.set(self._redis_key(namespace, key), json.dumps(payload, ensure_ascii=False), ex=ttl_seconds)


@lru_cache(maxsize=4)
def get_sqlite_json_cache(db_path: str) -> SQLiteJsonCache:
    return SQLiteJsonCache(db_path)


@lru_cache(maxsize=4)
def get_redis_json_cache(redis_url: str) -> RedisJsonCache:
    return RedisJsonCache(redis_url)
