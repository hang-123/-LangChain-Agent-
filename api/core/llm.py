from __future__ import annotations

from typing import Any, TypeVar

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from api.core.settings import get_settings

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # type: ignore
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore
    OpenAIEmbeddings = None  # type: ignore


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def get_chat_model(*, temperature: float = 0.1, streaming: bool = False) -> Any:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not api_key:
        raise RuntimeError("LLM not configured: missing OPENAI_API_KEY / QUERY_ENGINE_API_KEY / DASHSCOPE_API_KEY.")
    if ChatOpenAI is None:
        raise RuntimeError("langchain-openai is not installed.")

    return ChatOpenAI(
        model=settings.openai_model,
        temperature=temperature,
        api_key=api_key,
        base_url=settings.openai_base_url,
        streaming=streaming,
    )


def get_embedding_model() -> Any:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not api_key:
        raise RuntimeError("Embedding model not configured: missing OPENAI_API_KEY / QUERY_ENGINE_API_KEY / DASHSCOPE_API_KEY.")
    if OpenAIEmbeddings is None:
        raise RuntimeError("langchain-openai is not installed.")
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=api_key,
        base_url=settings.openai_base_url,
    )


async def embed_query(text: str) -> list[float]:
    model = get_embedding_model()
    if hasattr(model, "aembed_query"):
        return list(await model.aembed_query(text))
    return list(model.embed_query(text))


def coerce_message_text(payload: Any) -> str:
    content = getattr(payload, "content", payload)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
    return str(content)


async def invoke_structured_output(
    schema: type[SchemaT],
    *,
    system_prompt: str,
    human_prompt: str,
    variables: dict[str, Any],
    temperature: float = 0.1,
    config: RunnableConfig | None = None,
) -> SchemaT:
    llm = get_chat_model(temperature=temperature)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human_prompt),
        ]
    )

    if hasattr(llm, "with_structured_output"):
        try:
            chain = prompt | llm.with_structured_output(schema)
            result = await chain.ainvoke(variables, config=config)
            if isinstance(result, schema):
                return result
            return schema.model_validate(result)
        except Exception:
            pass

    parser = PydanticOutputParser(pydantic_object=schema)
    fallback_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt + "\n\nReturn JSON only. Follow this schema exactly:\n{format_instructions}",
            ),
            ("human", human_prompt),
        ]
    )
    chain = fallback_prompt.partial(format_instructions=parser.get_format_instructions()) | llm | parser
    return await chain.ainvoke(variables, config=config)
