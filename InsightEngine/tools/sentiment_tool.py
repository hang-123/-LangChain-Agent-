# InsightEngineLC/tools/sentiment_tool.py
import json
from langchain_core.prompts import ChatPromptTemplate
from InsightEngine.llms.base import get_llm
from InsightEngine.prompts.prompts import SENTIMENT_SYSTEM_PROMPT


def analyze_sentiment_distribution(raw_docs: str) -> dict:
    """
    返回 {"positive": int, "neutral": int, "negative": int}
    """
    if not raw_docs.strip():
        return {"positive": 0, "neutral": 0, "negative": 0}

    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SENTIMENT_SYSTEM_PROMPT),
            (
                "user",
                (
                    "以下是合并后的舆情片段：\n"
                    "------------------\n"
                    "{docs}\n"
                    "------------------\n\n"
                    "请以 JSON 形式输出情感分布，例如：\n"
                    "{{\n"
                    "  \"positive\": 10,\n"
                    "  \"neutral\": 5,\n"
                    "  \"negative\": 7\n"
                    "}}\n"
                    # "不要添加其他说明文字。"
                ),
            ),
        ]
    )

    chain = prompt | llm
    msg = chain.invoke({"docs": raw_docs})
    text = getattr(msg, "content", str(msg))

    # 简单 JSON 解析 + 兜底
    start, end = text.find("{"), text.rfind("}")
    json_text = text[start : end + 1] if start != -1 and end != -1 else text
    try:
        data = json.loads(json_text)
    except Exception:
        return {"positive": 0, "neutral": 0, "negative": 0}

    def to_int(x):  # 防御性转换
        try:
            return int(x)
        except Exception:
            return 0

    return {
        "positive": to_int(data.get("positive", 0)),
        "neutral": to_int(data.get("neutral", 0)),
        "negative": to_int(data.get("negative", 0)),
    }
