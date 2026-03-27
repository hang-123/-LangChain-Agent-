from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class ForumEngineConfig(BaseSettings):
    """Lightweight settings for the orchestrator."""

    save_individual_reports: bool = Field(True, alias="FORUM_SAVE_AGENT_REPORTS")
    log_dir: Path = Field(default=Path("logs"), alias="FORUM_LOG_DIR")
    # 是否启用简单会话记忆，默认开启
    use_memory: bool = Field(True, alias="FORUM_USE_MEMORY")
    memory_history_limit: int = Field(8, alias="FORUM_MEMORY_HISTORY_LIMIT")
    memory_max_chars: int = Field(1200, alias="FORUM_MEMORY_MAX_CHARS")

    model_config = {
        "env_file": (".env", "config.env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
