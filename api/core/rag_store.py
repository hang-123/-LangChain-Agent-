from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from api.core.llm import embed_query
from api.core.settings import get_settings

try:  # pragma: no cover - import depends on optional runtime package
    import psycopg
    from pgvector.psycopg import register_vector
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore
    register_vector = None  # type: ignore


ALLOWED_SOURCE_TYPES = {"jd", "company_profile", "interview", "tech_stack", "salary_culture"}


@dataclass(frozen=True)
class JobDocument:
    document_id: str
    source_type: str
    title: str
    url: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    document_id: str
    source_type: str
    title: str
    url: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RagSearchHit:
    chunk: RagChunk
    score: float
    updated_at: str = ""  # NEW: ISO timestamp for freshness decay


class RagSearchStore(Protocol):
    async def search(self, *, query: str, profile: dict[str, Any], top_k: int) -> list[RagSearchHit]: ...


def normalize_source_type(source_type: str) -> str:
    normalized = str(source_type or "").strip()
    if normalized not in ALLOWED_SOURCE_TYPES:
        raise ValueError(f"unsupported job document source_type: {source_type}")
    return normalized


def chunk_job_document(document: JobDocument, *, chunk_size: int = 900) -> list[RagChunk]:
    source_type = normalize_source_type(document.source_type)
    text = " ".join(str(document.content or "").split())
    if not text:
        return []
    chunks: list[RagChunk] = []
    for index, start in enumerate(range(0, len(text), chunk_size), start=1):
        chunk_text = text[start : start + chunk_size].strip()
        if not chunk_text:
            continue
        chunks.append(
            RagChunk(
                chunk_id=f"{document.document_id}::chunk::{index}",
                document_id=document.document_id,
                source_type=source_type,
                title=document.title,
                url=document.url,
                text=chunk_text,
                metadata=dict(document.metadata or {}),
            )
        )
    return chunks


class RagStore:
    def __init__(self, database_url: str, *, embedding_dim: int = 1536) -> None:
        self.database_url = database_url
        self.embedding_dim = embedding_dim

    def _connect(self):
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        connection = psycopg.connect(self.database_url)
        if register_vector is not None:
            register_vector(connection)
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS job_documents (
                        document_id TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS job_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES job_documents(document_id) ON DELETE CASCADE,
                        source_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({int(self.embedding_dim)}) NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_chunks_source_type ON job_chunks(source_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_chunks_metadata ON job_chunks USING GIN(metadata)")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_job_chunks_embedding ON job_chunks USING ivfflat (embedding vector_cosine_ops)"
                )

    async def upsert_job_document(self, document: JobDocument) -> list[RagChunk]:
        chunks = chunk_job_document(document)
        if not chunks:
            return []
        embeddings = [await embed_query(chunk.text) for chunk in chunks]
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO job_documents (document_id, source_type, title, url, content, metadata, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT(document_id) DO UPDATE SET
                        source_type = excluded.source_type,
                        title = excluded.title,
                        url = excluded.url,
                        content = excluded.content,
                        metadata = excluded.metadata,
                        updated_at = now()
                    """,
                    (
                        document.document_id,
                        normalize_source_type(document.source_type),
                        document.title,
                        document.url,
                        document.content,
                        document.metadata,
                    ),
                )
                cursor.execute("DELETE FROM job_chunks WHERE document_id = %s", (document.document_id,))
                for chunk, embedding in zip(chunks, embeddings):
                    cursor.execute(
                        """
                        INSERT INTO job_chunks (
                            chunk_id, document_id, source_type, title, url, text, metadata, embedding, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.source_type,
                            chunk.title,
                            chunk.url,
                            chunk.text,
                            chunk.metadata,
                            embedding,
                        ),
                    )
        return chunks

    async def search(self, *, query: str, profile: dict[str, Any], top_k: int) -> list[RagSearchHit]:
        query_text = " ".join(
            [
                str(query or ""),
                str(profile.get("company") or ""),
                str(profile.get("role") or ""),
                str(profile.get("team_hint") or ""),
                str(profile.get("domain_hint") or ""),
            ]
        ).strip()
        embedding = await embed_query(query_text)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT chunk_id, document_id, source_type, title, url, text, metadata,
                           1 - (embedding <=> %s) AS score,
                           updated_at
                    FROM job_chunks
                    WHERE source_type = ANY(%s)
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (embedding, list(ALLOWED_SOURCE_TYPES), embedding, int(top_k)),
                )
                rows = cursor.fetchall()
        hits: list[RagSearchHit] = []
        for row in rows:
            chunk_id, document_id, source_type, title, url, text, metadata, score, updated_at = row
            hits.append(
                RagSearchHit(
                    chunk=RagChunk(
                        chunk_id=str(chunk_id),
                        document_id=str(document_id),
                        source_type=normalize_source_type(str(source_type)),
                        title=str(title),
                        url=str(url),
                        text=str(text),
                        metadata=dict(metadata or {}),
                    ),
                    score=float(score or 0.0),
                    updated_at=str(updated_at or ""),
                )
            )
        return hits

    async def search_with_freshness(
        self, *, query: str, profile: dict[str, Any], top_k: int
    ) -> list[RagSearchHit]:
        """Search with freshness decay applied per spec 04 section 3.3."""
        from datetime import datetime, timezone

        hits = await self.search(query=query, profile=profile, top_k=top_k)
        now = datetime.now(timezone.utc)

        for hit in hits:
            if not hit.updated_at:
                continue
            try:
                updated_str = str(hit.updated_at)[:19]
                updated = datetime.strptime(updated_str, "%Y-%m-%dT%H:%M:%S")
                updated = updated.replace(tzinfo=timezone.utc)
                days = max(0, (now - updated).days)
                freshness = max(0, 100 - days * 2)

                if freshness >= 80:
                    pass  # No decay
                elif freshness >= 60:
                    object.__setattr__(hit, 'score', hit.score * 0.85)
                elif freshness >= 40:
                    object.__setattr__(hit, 'score', hit.score * 0.7)
                else:
                    object.__setattr__(hit, 'score', hit.score * 0.5)
            except (ValueError, TypeError):
                pass

        return hits


def build_rag_store() -> RagStore | None:
    settings = get_settings()
    if not settings.enable_rag:
        return None
    database_url = str(settings.rag_database_url or "").strip()
    if not database_url:
        return None
    return RagStore(database_url, embedding_dim=int(settings.embedding_dim or 1536))


async def safe_search_rag(
    *,
    store: RagSearchStore | None,
    query: str,
    profile: dict[str, Any],
    top_k: int,
) -> tuple[list[RagSearchHit], list[str]]:
    if store is None:
        return [], []
    try:
        return await store.search(query=query, profile=profile, top_k=top_k), []
    except Exception as exc:
        return [], [f"rag:{exc}"]


async def search_rag_sources(*, query: str, profile: dict[str, Any], top_k: int) -> tuple[list[RagSearchHit], list[str]]:
    store = build_rag_store()
    return await safe_search_rag(store=store, query=query, profile=profile, top_k=top_k)


async def auto_writeback(evidence_items: list[dict[str, Any]], quality_threshold: int = 70) -> int:
    """Phase 2: Auto-writeback high-quality Tavily results to pgvector.

    Returns number of items written back.
    """
    settings = get_settings()
    if not settings.enable_rag or not settings.enable_rag_writeback:
        return 0

    store = build_rag_store()
    if store is None:
        return 0

    count = 0
    for item in evidence_items:
        quality = int(item.get("quality_score", 0))
        if quality < quality_threshold:
            continue
        source_type = str(item.get("source_class", ""))
        if source_type not in ALLOWED_SOURCE_TYPES:
            continue
        snippet = str(item.get("snippet", ""))
        title = str(item.get("title", ""))
        url = str(item.get("url", ""))
        if not snippet.strip():
            continue
        doc_id = f"auto::{url}" if url else f"auto::{title}"
        try:
            document = JobDocument(
                document_id=doc_id,
                source_type=source_type,
                title=title,
                url=url,
                content=snippet,
            )
            await store.upsert_job_document(document)
            count += 1
        except Exception:
            continue
    return count
