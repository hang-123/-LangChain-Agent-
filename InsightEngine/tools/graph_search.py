from __future__ import annotations

"""
Lightweight knowledge-graph style search on top of PostgreSQL.

约定两张表（需要你在 PG 中建表，见说明）：
  - kg_entities(id UUID, name TEXT, type TEXT, created_at, updated_at)
  - kg_relations(id UUID, head_id UUID, tail_id UUID, rel_type TEXT,
                 source TEXT, confidence DOUBLE PRECISION, created_at)

本模块只做只读查询，失败时返回空列表，不阻塞主流程。
"""

from dataclasses import dataclass
from typing import List

from sqlalchemy import text

from utils.conversation_store import get_engine


@dataclass
class KGRelation:
    head: str
    relation: str
    tail: str
    direction: str  # "out" 表示 head->tail, "in" 表示 head<-tail
    source: str | None = None
    confidence: float | None = None


def search_kg_for_topic(topic: str, limit: int = 16) -> List[KGRelation]:
    """
    按主题关键字在 kg_entities / kg_relations 中查找相关实体及其关系。

    返回 head-relation-tail 形式的结构化结果，用于下游 LLM 参考。
    """

    topic = (topic or "").strip()
    if not topic:
        return []

    try:
        engine = get_engine()
    except Exception as exc:  # pragma: no cover - 防御性
        print(f"[KG] failed to get engine: {exc}")
        return []

    try:
        with engine.begin() as conn:
            # 1. 找到名称中包含 topic 的若干实体
            entities = conn.execute(
                text(
                    "SELECT id, name, type "
                    "FROM kg_entities "
                    "WHERE name ILIKE :kw "
                    "ORDER BY length(name) ASC "
                    "LIMIT 3"
                ),
                {"kw": f"%{topic}%"},
            ).fetchall()

            if not entities:
                return []

            per_entity = max(limit // max(len(entities), 1), 1)
            results: List[KGRelation] = []

            for ent_id, ent_name, _ent_type in entities:
                # 2a. 以该实体为 head 的关系：ent -> other
                rows_out = conn.execute(
                    text(
                        "SELECT e1.name AS head_name, r.rel_type, e2.name AS tail_name, "
                        "       r.source, r.confidence "
                        "FROM kg_relations r "
                        "JOIN kg_entities e1 ON r.head_id = e1.id "
                        "JOIN kg_entities e2 ON r.tail_id = e2.id "
                        "WHERE e1.id = :eid "
                        "LIMIT :lim"
                    ),
                    {"eid": ent_id, "lim": per_entity},
                ).fetchall()
                for head_name, rel_type, tail_name, source, conf in rows_out:
                    results.append(
                        KGRelation(
                            head=head_name,
                            relation=rel_type,
                            tail=tail_name,
                            direction="out",
                            source=source,
                            confidence=float(conf) if conf is not None else None,
                        )
                    )
                    if len(results) >= limit:
                        return results

                # 2b. 以该实体为 tail 的关系：other -> ent
                rows_in = conn.execute(
                    text(
                        "SELECT e2.name AS head_name, r.rel_type, e1.name AS tail_name, "
                        "       r.source, r.confidence "
                        "FROM kg_relations r "
                        "JOIN kg_entities e1 ON r.tail_id = e1.id "
                        "JOIN kg_entities e2 ON r.head_id = e2.id "
                        "WHERE e1.id = :eid "
                        "LIMIT :lim"
                    ),
                    {"eid": ent_id, "lim": per_entity},
                ).fetchall()
                for head_name, rel_type, tail_name, source, conf in rows_in:
                    results.append(
                        KGRelation(
                            head=head_name,
                            relation=rel_type,
                            tail=tail_name,
                            direction="in",
                            source=source,
                            confidence=float(conf) if conf is not None else None,
                        )
                    )
                    if len(results) >= limit:
                        return results

        return results[:limit]
    except Exception as exc:  # pragma: no cover - 防御性
        print(f"[KG] search_kg_for_topic failed: {exc}")
        return []

