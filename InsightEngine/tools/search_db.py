"""
DB-style helper tools for InsightEngine.

目前底层主要依赖 PGVector 向量库和本地文档，封装为更语义化的查询接口，
方便在节点链或其他 Agent 中按“话题”视角调用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from InsightEngine.tools.vector_store_pg import search_similar_docs


@dataclass
class DBSearchResult:
    source: str
    snippet: str


def search_topic_globally(topic: str, *, k: int = 8) -> List[DBSearchResult]:
    """
    以“话题”视角在内部知识库中检索相关内容。

    当前实现是对 PGVector 中的向量文档做相似度搜索，再将结果拆分成结构化条目。
    """
    merged = search_similar_docs(topic, k=k)
    if not merged or "No similar documents" in merged:
        return []

    results: List[DBSearchResult] = []
    for block in merged.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        # 简单解析 "[source]\n内容" 结构
        if block.startswith("[") and "]" in block:
            src_end = block.find("]")
            source = block[1:src_end]
            content = block[src_end + 1 :].strip()
        else:
            source = "vector_store"
            content = block

        results.append(DBSearchResult(source=source, snippet=content))
    return results

