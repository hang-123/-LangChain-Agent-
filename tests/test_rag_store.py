from __future__ import annotations

import pytest

from api.core.rag_store import (
    JobDocument,
    RagChunk,
    RagSearchHit,
    chunk_job_document,
    normalize_source_type,
    safe_search_rag,
)


def test_chunk_job_document_preserves_metadata_and_allowed_source_type():
    document = JobDocument(
        document_id="doc_001",
        source_type="jd",
        title="后端开发实习 JD",
        url="https://example.com/jd",
        content="熟悉 Redis、MySQL。\n需要理解缓存设计和消息队列。",
        metadata={"company": "字节跳动"},
    )

    chunks = chunk_job_document(document, chunk_size=16)

    assert chunks
    assert chunks[0].document_id == "doc_001"
    assert chunks[0].source_type == "jd"
    assert chunks[0].metadata["company"] == "字节跳动"


def test_normalize_source_type_rejects_non_job_corpus():
    assert normalize_source_type("company_profile") == "company_profile"
    with pytest.raises(ValueError, match="unsupported job document source_type"):
        normalize_source_type("project_doc")


@pytest.mark.asyncio
async def test_safe_search_rag_returns_hits_and_failures_without_raising():
    class FakeStore:
        async def search(self, *, query, profile, top_k):
            assert query == "字节后端实习"
            assert profile["company"] == "字节跳动"
            assert top_k == 2
            return [
                RagSearchHit(
                    chunk=RagChunk(
                        chunk_id="chunk_001",
                        document_id="doc_001",
                        source_type="jd",
                        title="后端开发实习 JD",
                        url="https://example.com/jd",
                        text="熟悉 Redis 和 MySQL",
                        metadata={"company": "字节跳动"},
                    ),
                    score=0.91,
                )
            ]

    hits, failures = await safe_search_rag(
        store=FakeStore(),
        query="字节后端实习",
        profile={"company": "字节跳动"},
        top_k=2,
    )

    assert failures == []
    assert hits[0].chunk.source_type == "jd"


@pytest.mark.asyncio
async def test_safe_search_rag_downgrades_store_errors_to_failures():
    class FailingStore:
        async def search(self, *, query, profile, top_k):
            raise RuntimeError("pgvector unavailable")

    hits, failures = await safe_search_rag(
        store=FailingStore(),
        query="字节后端实习",
        profile={},
        top_k=3,
    )

    assert hits == []
    assert failures == ["rag:pgvector unavailable"]
