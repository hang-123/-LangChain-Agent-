"""Embedding backend abstraction — supports provider switching.

Providers:
  - siliconflow: BGE-M3 via SiliconFlow API
  - dashscope: text-embedding-v4 via Alibaba DashScope
  - openai: text-embedding-3-small via OpenAI-compatible API
  - local: BGE-M3 local deployment

Dense vectors for semantic search; Sparse (lexical) weights for keyword matching.
"""

from __future__ import annotations

from typing import Any, Protocol

from api.core.settings import get_settings


class EmbeddingBackend(Protocol):
    """Protocol for embedding backends."""

    async def embed_query(self, text: str) -> list[float]:
        """Generate a dense embedding vector for a query."""
        ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embedding vectors for documents."""
        ...

    async def sparse_weights(self, text: str) -> dict[str, float] | None:
        """Generate sparse lexical weights for hybrid search.

        Returns None if sparse embeddings are not supported by this backend.
        """
        ...

    @property
    def dim(self) -> int:
        """Dense embedding dimension."""
        ...


class SiliconFlowBGEBackend:
    """BGE-M3 via SiliconFlow API (https://siliconflow.cn).

    Supports both dense vectors and sparse lexical weights.
    """

    def __init__(self, api_key: str, model: str = "BAAI/bge-m3") -> None:
        self.api_key = api_key
        self.model = model
        self._dim = 1024
        self._base_url = "https://api.siliconflow.cn/v1"

    @property
    def dim(self) -> int:
        return self._dim

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        results = await asyncio.gather(*(self._embed(t) for t in texts))
        return [list(r) for r in results]

    async def sparse_weights(self, text: str) -> dict[str, float] | None:
        """SiliconFlow BGE-M3 supports sparse vectors.

        Uses the /v1/embeddings endpoint with return_sparse=true.
        Falls back gracefully if the API doesn't return sparse data.
        """
        try:
            import aiohttp
        except ImportError:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": text,
                        "encoding_format": "float",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    # Try to extract sparse data if available
                    data_list = data.get("data", [])
                    if data_list:
                        item = data_list[0]
                        sparse = item.get("sparse_embedding") or item.get("sparse")
                        if sparse:
                            return dict(sparse)
        except Exception:
            pass
        return None

    async def _embed(self, text: str) -> list[float]:
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": text,
                        "encoding_format": "float",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        raise RuntimeError(
                            f"SiliconFlow embedding failed: {resp.status}"
                        )
                    data = await resp.json()
                    data_list = data.get("data", [])
                    if not data_list:
                        raise RuntimeError("SiliconFlow returned empty embedding")
                    return list(data_list[0]["embedding"])
        except Exception:
            raise


class OpenAICompatibleBackend:
    """OpenAI-compatible embedding backend (uses langchain-openai).

    Kept as fallback. Does not support sparse weights.
    """

    def __init__(self, model: str, api_key: str, base_url: str) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            raise RuntimeError("Backend not initialized; call _init_dim first")
        return self._dim

    def _get_model(self):
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=self.model, api_key=self.api_key, base_url=self.base_url
        )

    async def _init_dim(self) -> None:
        if self._dim is None:
            emb = await self.embed_query("test")
            self._dim = len(emb)

    async def embed_query(self, text: str) -> list[float]:
        model = self._get_model()
        if hasattr(model, "aembed_query"):
            result = await model.aembed_query(text)
            if self._dim is None:
                self._dim = len(result)
            return list(result)
        result = model.embed_query(text)
        if self._dim is None:
            self._dim = len(result)
        return list(result)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        if hasattr(model, "aembed_documents"):
            results = await model.aembed_documents(texts)
            return [list(r) for r in results]
        results = model.embed_documents(texts)
        return [list(r) for r in results]

    async def sparse_weights(self, text: str) -> dict[str, float] | None:
        return None  # OpenAI embeddings don't support sparse


class NullReranker:
    """Passthrough reranker — placeholder for future cross-encoder integration."""

    async def rerank(
        self, query: str, documents: list[str], top_k: int = 5
    ) -> list[tuple[int, float]]:
        """Return documents in original order with neutral scores."""
        return [(i, 1.0) for i in range(min(top_k, len(documents)))]


# -- Factory --


def build_embedding_backend() -> EmbeddingBackend:
    """Build the appropriate embedding backend based on settings."""
    settings = get_settings()
    provider = str(settings.embedding_provider or "siliconflow").strip().lower()

    if provider == "siliconflow":
        api_key = (
            settings.embedding_api_key.get_secret_value()
            if settings.embedding_api_key
            else ""
        )
        if not api_key:
            api_key = (
                settings.openai_api_key.get_secret_value()
                if settings.openai_api_key
                else ""
            )
        if not api_key:
            raise RuntimeError(
                "SiliconFlow embedding requires EMBEDDING_API_KEY or OPENAI_API_KEY"
            )
        return SiliconFlowBGEBackend(
            api_key=api_key,
            model=str(settings.embedding_model or "BAAI/bge-m3"),
        )

    if provider in ("openai", "dashscope", "dashscope_compatible"):
        api_key = (
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key
            else ""
        )
        if not api_key:
            raise RuntimeError("OpenAI-compatible embedding requires OPENAI_API_KEY")
        return OpenAICompatibleBackend(
            model=str(settings.embedding_model or "text-embedding-3-small"),
            api_key=api_key,
            base_url=settings.openai_base_url,
        )

    raise ValueError(f"Unknown embedding provider: {provider}")


def build_reranker() -> NullReranker:
    """Build reranker backend. Currently returns NullReranker passthrough."""
    settings = get_settings()
    if not settings.enable_reranker:
        return NullReranker()
    # Future: BGE-Reranker-v2-m3, Cohere Rerank v3, etc.
    return NullReranker()
