from __future__ import annotations

from langchain_openai import ChatOpenAI

from ReportEngine.config import ReportEngineConfig


def build_llm(config: ReportEngineConfig) -> ChatOpenAI:
    kwargs = {
        "model": config.llm_model_name,
        "temperature": config.temperature,
    }
    if config.llm_api_key:
        kwargs["api_key"] = config.llm_api_key
    if config.llm_base_url:
        kwargs["base_url"] = config.llm_base_url
    return ChatOpenAI(**kwargs)

