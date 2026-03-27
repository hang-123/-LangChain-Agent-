from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field

from QueryEngine.config import QueryEngineSettings


class ReportEngineSettings(QueryEngineSettings):
    """Shared settings for the reporting pipeline."""

    output_dir: Path = Field(default=Path("final_reports"), alias="REPORT_OUTPUT_DIR")
    max_sections: int = Field(5, alias="REPORT_MAX_SECTIONS")
    template_id: str = Field("default", alias="REPORT_TEMPLATE_ID")
    llm_model_name: str = Field(
        ...,
        validation_alias=AliasChoices("REPORT_LLM_MODEL_NAME", "QUERY_ENGINE_MODEL_NAME"),
    )
    llm_api_key: str = Field(
        ...,
        validation_alias=AliasChoices("REPORT_LLM_API_KEY", "QUERY_ENGINE_API_KEY"),
    )
    llm_base_url: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("REPORT_LLM_BASE_URL", "QUERY_ENGINE_BASE_URL"),
    )


class ReportEngineConfig(ReportEngineSettings):
    temperature: float = Field(
        0.1,
        validation_alias=AliasChoices("REPORT_TEMPERATURE", "QUERY_ENGINE_TEMPERATURE"),
    )

    @classmethod
    def from_env(cls) -> "ReportEngineConfig":
        cfg = cls()
        cfg.validate_required()
        return cfg
