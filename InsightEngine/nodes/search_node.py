# InsightEngineLC/nodes/search_node.py
from InsightEngine.nodes.base_node import BaseNode
from InsightEngine.state.state import InsightState
from InsightEngine.tools.local_search import search_local_docs_by_keyword
from InsightEngine.tools.vector_store_pg import get_retriever
from InsightEngine.tools.keyword_optimizer import optimize_keywords
from InsightEngine.tools.search_db import search_topic_globally
from InsightEngine.tools.graph_search import search_kg_for_topic


class SearchNode(BaseNode):
    name = "search_node"
    # True: 使用 PG 向量检索；False: 使用本地关键词检索
    USE_VECTOR_SEARCH = True

    def run(self, state: InsightState) -> InsightState:
        if not state.keywords:
            state.keywords = optimize_keywords(state.question)
        print(f"[SearchNode] 关键词：{state.keywords}")

        use_vector = self.USE_VECTOR_SEARCH
        docs = []

        if use_vector:
            try:
                retriever = get_retriever(k=8)
                docs = retriever.invoke(state.question)
            except Exception as exc:  # pragma: no cover
                print(f"[SearchNode] 向量检索异常，改走本地关键词检索。原因：{exc}")
                use_vector = False

        merged_chunks = []

        if use_vector and docs:
            state.documents = []
            for d in docs:
                meta = getattr(d, "metadata", {}) or {}
                src = meta.get("source") or "unknown"
                content = getattr(d, "page_content", str(d))
                state.documents.append({"page_content": content, "metadata": meta})
                merged_chunks.append(f"[{src}]\n{content}")
        else:
            # fallback: keyword search + concatenated text
            state.documents = []
            for kw in state.keywords:
                snippet = search_local_docs_by_keyword.run(kw)
                merged_chunks.append(f"【关键词：{kw}】\n{snippet}")

        # 追加 DB 风格的话题检索结果（当前用 PGVector 模拟）
        try:
            db_results = search_topic_globally(state.question, k=6)
        except Exception as exc:  # pragma: no cover
            print(f"[SearchNode] DB topic search failed: {exc}")
            db_results = []

        state.db_results = [{"source": r.source, "snippet": r.snippet} for r in db_results]
        for r in db_results:
            merged_chunks.append(f"[DB:{r.source}]\n{r.snippet}")

        # 追加知识图谱结构化事实（如果存在 KG 表）
        try:
            kg_relations = search_kg_for_topic(state.question, limit=10)
        except Exception as exc:  # pragma: no cover
            print(f"[SearchNode] KG search failed: {exc}")
            kg_relations = []

        kg_facts = []
        for rel in kg_relations:
            fact = {
                "head": rel.head,
                "relation": rel.relation,
                "tail": rel.tail,
                "direction": rel.direction,
                "source": rel.source,
                "confidence": rel.confidence,
            }
            kg_facts.append(fact)
            arrow = "->" if rel.direction == "out" else "<-"
            merged_chunks.append(
                f"[KG] {rel.head} -[{rel.relation}]{arrow} {rel.tail} "
                f"(source={rel.source or '-'}, conf={rel.confidence if rel.confidence is not None else '-'})"
            )
        state.kg_facts = kg_facts

        state.raw_docs = "\n\n".join(chunk for chunk in merged_chunks if chunk.strip())

        return state
