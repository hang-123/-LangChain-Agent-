from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field

from QueryEngine.config import QueryEngineSettings


class MediaEngineSettings(QueryEngineSettings):
    """Reuse QueryEngine settings but customize output and knobs."""

    # 单次媒体检索的最大条数，默认比 QueryEngine 更紧一些，避免多模态场景 token 暴涨
    max_media_items: int = Field(8, alias="MEDIA_MAX_ITEMS")
    include_images: bool = Field(True, alias="MEDIA_INCLUDE_IMAGES")
    output_dir: Path = Field(default=Path("media_reports"), alias="MEDIA_OUTPUT_DIR")
    llm_model_name: str = Field(
        ...,
        validation_alias=AliasChoices("MEDIA_LLM_MODEL_NAME", "QUERY_ENGINE_MODEL_NAME"),
    )
    llm_api_key: str = Field(
        ...,
        validation_alias=AliasChoices("MEDIA_LLM_API_KEY", "QUERY_ENGINE_API_KEY"),
    )
    llm_base_url: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("MEDIA_LLM_BASE_URL", "QUERY_ENGINE_BASE_URL"),
    )


class MediaEngineConfig(MediaEngineSettings):
    temperature: float = Field(
        0.2,
        validation_alias=AliasChoices("MEDIA_TEMPERATURE", "QUERY_ENGINE_TEMPERATURE"),
    )

    @classmethod
    def from_env(cls) -> "MediaEngineConfig":
        cfg = cls()
        cfg.validate_required()
        return cfg
