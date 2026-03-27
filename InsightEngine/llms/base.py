from langchain_openai import ChatOpenAI
from InsightEngine.utils.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME

def get_llm():
    """返回一个统一封装的 LLM 客户端，方便以后替换模型供应商。"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY 未配置，请在 .env 中设置。")

    llm = ChatOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL_NAME,
        temperature=0.2,
    )
    return llm