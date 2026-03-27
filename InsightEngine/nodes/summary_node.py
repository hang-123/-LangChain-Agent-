# InsightEngineLC/nodes/summary_node.py
from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from InsightEngine.nodes.base_node import BaseNode
from InsightEngine.state.state import InsightState, InsightReport
from InsightEngine.llms.base import get_llm
from InsightEngine.prompts.prompts import SUMMARY_SYSTEM_PROMPT


def _format_docs(documents: List[dict], fallback: str) -> str:
    if not documents:
        return fallback
    lines = []
    for doc in documents:
        meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
        src = meta.get("source") or "unknown"
        content = doc.get("page_content", "") if isinstance(doc, dict) else str(doc)
        lines.append(f"[{src}]\n{content}")
    return "\n\n".join(lines) or fallback


class SummaryLLMOutput(BaseModel):
    main_concerns: List[str] = Field(default_factory=list)
    positive_points: List[str] = Field(default_factory=list)
    negative_points: List[str] = Field(default_factory=list)
    sentiment_summary: str = ""
    risks: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class SummaryNode(BaseNode):
    name = "summary_node"

    def run(self, state: InsightState) -> InsightState:
        llm = get_llm()
        docs_text = _format_docs(state.documents, state.raw_docs or "（暂无数据）")

        db_block = ""
        if getattr(state, "db_results", None):
            lines = []
            for item in state.db_results[:10]:
                src = item.get("source", "db")
                snippet = item.get("snippet", "")
                if not snippet:
                    continue
                lines.append(f"[{src}]\n{snippet}")
            if lines:
                db_block = "\n\n".join(lines)

        kg_block = ""
        if getattr(state, "kg_facts", None):
            lines = []
            for fact in state.kg_facts[:12]:
                head = fact.get("head", "")
                rel = fact.get("relation", "")
                tail = fact.get("tail", "")
                direction = fact.get("direction", "out")
                source = fact.get("source") or "-"
                conf = fact.get("confidence")
                arrow = "->" if direction == "out" else "<-"
                conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "-"
                if not head or not rel or not tail:
                    continue
                lines.append(f"{head} -[{rel}]{arrow} {tail} (source={source}, conf={conf_str})")
            if lines:
                kg_block = "\n".join(lines)

        parser = PydanticOutputParser(pydantic_object=SummaryLLMOutput)
        prompt = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", SUMMARY_SYSTEM_PROMPT + "\n{format_instructions}"),
                    (
                        "user",
                        "用户问题：{question}\n\n"
                        "一、向量/本地文档片段（已合并多份文档）：\n"
                        "------------------\n"
                        "{docs}\n"
                        "------------------\n\n"
                        "二、内部数据库话题检索片段（如有）：\n"
                        "------------------\n"
                        "{db_snippets}\n"
                        "------------------\n\n"
                        "三、知识图谱结构化事实（如有）：\n"
                        "------------------\n"
                        "{kg_snippets}\n"
                        "------------------\n\n"
                        "请基于以上全部证据输出结构化洞察。",
                    ),
                ]
            ).partial(format_instructions=parser.get_format_instructions())
        )

        chain = prompt | llm | parser
        try:
            summary: SummaryLLMOutput = chain.invoke(
                {
                    "question": state.question,
                    "docs": docs_text,
                    "db_snippets": db_block or "（暂无 DB 片段）",
                    "kg_snippets": kg_block or "（暂无知识图谱事实）",
                }
            )
            state.report = InsightReport(
                question=state.question,
                keywords=state.keywords,
                main_concerns=summary.main_concerns,
                positive_points=summary.positive_points,
                negative_points=summary.negative_points,
                sentiment_summary=summary.sentiment_summary,
                risks=summary.risks,
                suggestions=summary.suggestions,
            )
        except Exception as exc:  # pragma: no cover
            print(f"[SummaryNode] 结构化解析失败，返回原始文本。原因：{exc}")
            state.report = InsightReport(
                question=state.question,
                keywords=state.keywords,
                main_concerns=[docs_text[:500]],
            )
        return state

