# InsightEngineLC/tools/vector_store_pg.py
from __future__ import annotations

from dataclasses import dataclass
import inspect
from pathlib import Path
from typing import Sequence

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import create_engine

try:
    from langchain_postgres.vectorstores import PGVector
except ImportError as _pg_err:  # pragma: no cover
    PGVector = None  # type: ignore[assignment]
    _PGVECTOR_IMPORT_ERROR = _pg_err

from InsightEngine.utils.config import (
    LOCAL_DOCS_DIR,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    PG_COLLECTION_NAME,
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_USER,
)


@dataclass(frozen=True)
class PGVectorConfig:
    """Typed container for PGVector connectivity settings."""

    host: str = PG_HOST
    port: int = PG_PORT
    database: str = PG_DB
    user: str = PG_USER
    password: str = PG_PASSWORD
    collection_name: str = PG_COLLECTION_NAME
    driver: str = "psycopg"  # langchain_postgres only supports psycopg3
    use_jsonb: bool = True

    def connection_string(self) -> str:
        return PGVector.connection_string_from_db_params(
            driver=self.driver,
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
        )

    def psycopg_kwargs(self) -> dict:
        """Return keyword arguments suitable for psycopg.connect."""

        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
        }


def _build_embeddings() -> OpenAIEmbeddings:
    """Create a shared embedding client for PGVector operations."""

    return OpenAIEmbeddings(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        model="text-embedding-v1",
        # 3. 这是一个保险措施，防止维度报错
        check_embedding_ctx_length=False
    )


def _load_source_documents(doc_dir: Path) -> list[Document]:
    """Load each *.txt file under doc_dir as a Document."""

    documents: list[Document] = []
    for path in sorted(doc_dir.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="gbk", errors="ignore")

        documents.append(Document(page_content=text, metadata={"source": path.name}))

    return documents


def _split_documents(
    documents: Sequence[Document], *, chunk_size: int, chunk_overlap: int
) -> list[Document]:
    if not documents:
        return []

    # 为了避免依赖额外的 text_splitter 包，这里实现一个简单的按字符切分逻辑。
    chunks: list[Document] = []
    for doc in documents:
        text = doc.page_content or ""
        meta = doc.metadata or {}
        if not text:
            continue
        start = 0
        length = len(text)
        step = max(chunk_size - chunk_overlap, 1)
        while start < length:
            end = min(start + chunk_size, length)
            chunk_text = text[start:end]
            chunks.append(Document(page_content=chunk_text, metadata=meta))
            if end == length:
                break
            start += step
    return chunks


def _call_pgvector_factory(
    factory,
    *,
    embeddings: OpenAIEmbeddings,
    config: PGVectorConfig,
    connection_string: str,
):
    """Adapt to signature changes across langchain_postgres releases."""

    params = inspect.signature(factory).parameters
    kwargs = {
        "collection_name": config.collection_name,
        "connection_string": connection_string,
        "use_jsonb": config.use_jsonb,
    }
    if "embedding" in params:
        kwargs["embedding"] = embeddings
    elif "embeddings" in params:
        kwargs["embeddings"] = embeddings
    else:  # pragma: no cover
        raise TypeError("Unsupported PGVector factory signature")

    return factory(**kwargs)


def get_vectorstore(
    config: PGVectorConfig | None = None,
    *,
    embeddings: OpenAIEmbeddings | None = None,
) -> PGVector:
    """Build a PGVector instance using the best available API."""

    if PGVector is None:
        raise RuntimeError(
            "PGVector backend is not available. Please install 'langchain-postgres' "
            "or disable vector search in InsightEngine."
        ) from _PGVECTOR_IMPORT_ERROR  # type: ignore[name-defined]

    config = config or PGVectorConfig()
    embeddings = embeddings or _build_embeddings()
    connection_string = config.connection_string()

    if hasattr(PGVector, "from_params"):
        return _call_pgvector_factory(
            PGVector.from_params,
            embeddings=embeddings,
            config=config,
            connection_string=connection_string,
        )

    # Fallback: use a SQLAlchemy engine (accepted by PGVector)
    engine = create_engine(connection_string)
    return PGVector(
        embeddings=embeddings,
        collection_name=config.collection_name,
        connection=engine,
        use_jsonb=config.use_jsonb,
    )


def get_retriever(
    *,
    k: int = 8,
    config: PGVectorConfig | None = None,
    embeddings: OpenAIEmbeddings | None = None,
):
    """
    Return a LangChain retriever backed by PGVector.
    """
    store = get_vectorstore(config=config, embeddings=embeddings)
    return store.as_retriever(search_kwargs={"k": k})


def index_local_docs(
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    doc_dir: Path | None = None,
    config: PGVectorConfig | None = None,
) -> None:
    """Chunk local documents and upsert them into PGVector."""

    doc_dir = doc_dir or LOCAL_DOCS_DIR
    config = config or PGVectorConfig()
    embeddings = _build_embeddings()

    raw_docs = _load_source_documents(doc_dir)
    chunked_docs = _split_documents(
        raw_docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    if not chunked_docs:
        print(f"[PGVector] No txt files found under {doc_dir}.")
        return

    store = get_vectorstore(config=config, embeddings=embeddings)
    print(
        f"[PGVector] Writing {len(chunked_docs)} chunks into collection {config.collection_name}..."
    )
    store.add_documents(chunked_docs)
    print("[PGVector] Upsert completed.")


def search_similar_docs(
    query: str,
    *,
    k: int = 8,
    config: PGVectorConfig | None = None,
) -> str:
    """Return merged snippets for downstream summarizers."""

    store = get_vectorstore(config=config)
    docs = store.similarity_search(query, k=k)

    if not docs:
        return "No similar documents found in vector store."

    return "\n\n".join(
        f"[{doc.metadata.get('source', 'unknown')}]\n{doc.page_content}" for doc in docs
    )


@tool
def search_vector_docs(query: str) -> str:
    """
    使用 PGVector 向量库检索内部文档，返回合并的文本片段。
    备注：依赖 index_local_docs 预先写入向量库。
    """
    return search_similar_docs(query)
