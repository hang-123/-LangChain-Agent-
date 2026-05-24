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


# Per-source-type chunking strategies
CHUNK_CONFIG: dict[str, dict[str, int]] = {
    "jd":              {"chunk_size": 0, "overlap": 0,   "strategy": "markdown_header"},
    "company_profile": {"chunk_size": 0, "overlap": 0,   "strategy": "markdown_header"},
    "interview":       {"chunk_size": 800, "overlap": 0, "strategy": "qa_pair"},
    "tech_stack":      {"chunk_size": 600, "overlap": 200, "strategy": "sentence"},
    "salary_culture":  {"chunk_size": 600, "overlap": 200, "strategy": "sentence"},
}


def _split_by_markdown_header(text: str) -> list[str]:
    """Split text by markdown headers (## or ###)."""
    import re
    sections = re.split(r'\n(?=#{2,3}\s)', text)
    return [s.strip() for s in sections if s.strip()]


def _split_by_qa_pair(text: str) -> list[str]:
    """Split text by Q&A pattern (Q: or A: lines)."""
    import re
    # Try Q&A splitting
    parts = re.split(r'\n(?=[Qq问][:：])', text)
    if len(parts) > 1:
        return [p.strip() for p in parts if p.strip()]
    # Fallback to sentence splitting
    return _split_by_sentence(text, 800, 0)


def _split_by_sentence(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text by sentences with configurable size and overlap."""
    import re
    sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    i = 0
    while i < len(sentences):
        chunk = ""
        while i < len(sentences) and len(chunk) + len(sentences[i]) <= chunk_size:
            chunk += sentences[i]
            i += 1
        if chunk:
            chunks.append(chunk)
        elif i < len(sentences):
            # Single sentence exceeds chunk_size, include as-is
            chunks.append(sentences[i])
            i += 1
        # Backtrack for overlap
        if overlap > 0 and i < len(sentences):
            overlap_chars = 0
            while i > 0 and overlap_chars < overlap:
                i -= 1
                overlap_chars += len(sentences[i])
    return chunks


def chunk_job_document(document: JobDocument, *, chunk_size: int = 0) -> list[RagChunk]:
    """Chunk a document using per-source-type strategy.

    chunk_size=0 means use the strategy-specific default from CHUNK_CONFIG.
    """
    source_type = normalize_source_type(document.source_type)
    text = str(document.content or "").strip()
    if not text:
        return []

    config = CHUNK_CONFIG.get(source_type, {"chunk_size": 900, "overlap": 0, "strategy": "fixed"})
    strategy = config["strategy"]
    effective_chunk_size = chunk_size if chunk_size > 0 else config.get("chunk_size", 900)
    overlap = config.get("overlap", 0)

    if strategy == "markdown_header":
        text_segments = _split_by_markdown_header(text)
    elif strategy == "qa_pair":
        text_segments = _split_by_qa_pair(text)
    elif strategy == "sentence":
        text_segments = _split_by_sentence(text, effective_chunk_size, overlap)
    else:
        # Fixed-size fallback
        normalized = " ".join(text.split())
        text_segments = [
            normalized[i:i + effective_chunk_size]
            for i in range(0, len(normalized), effective_chunk_size)
        ]

    chunks: list[RagChunk] = []
    for index, chunk_text in enumerate(text_segments, start=1):
        if not chunk_text.strip():
            continue
        chunks.append(
            RagChunk(
                chunk_id=f"{document.document_id}::chunk::{index}",
                document_id=document.document_id,
                source_type=source_type,
                title=document.title,
                url=document.url,
                text=chunk_text.strip(),
                metadata=dict(document.metadata or {}),
            )
        )
    return chunks


class RagStore:
    def __init__(self, database_url: str, *, embedding_dim: int = 1024) -> None:
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
                # Full-text search support for sparse/hybrid retrieval
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_job_chunks_text_fts "
                    "ON job_chunks USING GIN(to_tsvector('simple', text))"
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
        settings = get_settings()
        dense_weight = float(settings.rag_dense_weight or 0.7)
        sparse_weight = float(settings.rag_sparse_weight or 0.3)

        embedding = await embed_query(query_text)
        # Build keyword tokens for sparse full-text search
        keywords = _extract_search_keywords(query_text)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                if keywords:
                    # Hybrid: dense vector + sparse tsquery → RRF merged
                    cursor.execute(
                        """
                        SELECT chunk_id, document_id, source_type, title, url, text, metadata,
                               (%s * (1 - (embedding <=> %s)))
                               + (%s * ts_rank(to_tsvector('simple', text), plainto_tsquery('simple', %s)))
                               AS score,
                               updated_at
                        FROM job_chunks
                        WHERE source_type = ANY(%s)
                        ORDER BY score DESC
                        LIMIT %s
                        """,
                        (
                            dense_weight, embedding,
                            sparse_weight, " & ".join(keywords),
                            list(ALLOWED_SOURCE_TYPES), int(top_k),
                        ),
                    )
                else:
                    # Dense-only fallback
                    cursor.execute(
                        """
                        SELECT chunk_id, document_id, source_type, title, url, text, metadata,
                               (1 - (embedding <=> %s)) AS score,
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


def _extract_search_keywords(text: str) -> list[str]:
    """Extract meaningful keywords for full-text search."""
    import re
    # Split by whitespace and punctuation
    tokens = re.findall(r'[一-鿿]+|[a-zA-Z0-9]+', text.lower())
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'in', 'on', 'at', 'to', 'for', 'of', 'with', 'from', 'by',
        'and', 'or', 'not', 'but', 'if', 'then', 'else', 'when',
        'this', 'that', 'it', 'its', 'we', 'you', 'they',
        'role', 'position', 'team', 'work', 'job', 'candidate',
    }
    keywords = [t for t in tokens if len(t) >= 2 and t not in stopwords]
    return _unique(keywords)[:8]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result



def build_rag_store() -> RagStore | None:
    settings = get_settings()
    if not settings.enable_rag:
        return None
    database_url = str(settings.rag_database_url or "").strip()
    if not database_url:
        return None
    return RagStore(database_url, embedding_dim=int(settings.embedding_dim or 1024))


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


async def auto_writeback(
    evidence_items: list[dict[str, Any]],
    quality_threshold: int = 70,
    *,
    profile: dict[str, Any] | None = None,
    user_id: str = "",
) -> int:
    """Auto-writeback high-quality Tavily results to pgvector + LTM bridge.

    v2.0: quality>=80 + freshness>=70 items are also written to LTM
    as ENTITY_KNOWLEDGE memories.
    Returns number of items written back to RAG.
    """
    settings = get_settings()
    if not settings.enable_rag or not settings.enable_rag_writeback:
        return 0

    store = build_rag_store()
    if store is None:
        return 0

    profile = profile or {}
    ltm_count = 0
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

        # RAG → LTM bridge: high-quality results become entity knowledge
        freshness = int(item.get("freshness_score", 0))
        if quality >= 80 and freshness >= 70 and user_id:
            try:
                await _bridge_to_ltm(
                    user_id=user_id,
                    company=str(profile.get("company") or ""),
                    source_type=source_type,
                    snippet=snippet,
                    quality=quality,
                )
                ltm_count += 1
            except Exception:
                pass

    return count


async def _bridge_to_ltm(
    *, user_id: str, company: str, source_type: str, snippet: str, quality: int
) -> None:
    """Write a RAG hit to LTM as ENTITY_KNOWLEDGE."""
    from datetime import datetime, timedelta

    try:
        from api.core.memory.ltm_store import build_ltm_store
        from api.core.memory.models import LongTermMemory, MemoryType, MemoryStatus, SourceType

        ltm = build_ltm_store()
        if ltm is None:
            return

        import hashlib
        import uuid

        content = f"[{source_type}] {company}: {snippet[:300]}"
        memory = LongTermMemory(
            memory_id=f"rag-{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            memory_type=MemoryType.ENTITY_KNOWLEDGE,
            source_type=SourceType.RAG_WRITEBACK,
            content=content,
            structured_data={
                "company": company,
                "source_type": source_type,
                "quality_score": quality,
                "source": "rag_auto_writeback",
            },
            initial_importance=0.7,
            importance=0.7,
            lifetime_days=MemoryType.ENTITY_KNOWLEDGE.lifetime_days,
            status=MemoryStatus.ACTIVE,
            content_hash=hashlib.md5(content.encode()).hexdigest()[:12],
            expires_at=(datetime.utcnow() + timedelta(days=180)).isoformat(),
        )
        await ltm.save(memory)
    except Exception:
        pass  # LTM bridge failure is non-blocking
