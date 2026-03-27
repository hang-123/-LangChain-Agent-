# InsightEngineLC/tools/keyword_optimizer.py
from langchain_core.prompts import ChatPromptTemplate
from InsightEngine.llms.base import get_llm
from InsightEngine.prompts.prompts import KEYWORD_SYSTEM_PROMPT


def optimize_keywords(question: str) -> list[str]:
    """
    用 LLM 从问题里提取并优化关键词。
    现在是最小版：直接让模型吐关键词，然后自己解析。
    """
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", KEYWORD_SYSTEM_PROMPT),
            ("user", "用户问题：{question}\n请给出 2-5 个检索关键词。"),
        ]
    )
    chain = prompt | llm
    msg = chain.invoke({"question": question})
    text = getattr(msg, "content", str(msg))

    # 粗暴解析：按逗号/换行拆 + 去空白
    raw = text.replace("，", ",")
    parts = []
    for line in raw.splitlines():
        for piece in line.split(","):
            piece = piece.strip(" 、,;，。.!?？")
            if piece:
                parts.append(piece)

    return parts[:5]
