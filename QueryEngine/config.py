# config_langchain.py
from typing import Optional
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class QueryEngineSettings(BaseSettings):
    """Query Engine 配置（LangChain 版本）"""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "config.env"),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # ====== LLM 相关 ======
    llm_api_key: str = Field(..., alias="QUERY_ENGINE_API_KEY")
    llm_base_url: Optional[str] = Field(None, alias="QUERY_ENGINE_BASE_URL")
    llm_model_name: str = Field(..., alias="QUERY_ENGINE_MODEL_NAME")
    # 兼容字段，默认等于模型名
    llm_provider: Optional[str] = None

    # ====== Tavily 搜索相关 ======
    tavily_api_key: str = Field(..., alias="TAVILY_API_KEY")

    # ====== 查询控制参数 ======
    search_timeout: int = Field(240, alias="SEARCH_TIMEOUT")
    # 下游拼接到 prompt 里的内容最大长度（字符级粗控），防止 token 过多
    max_content_length: int = Field(16000, alias="SEARCH_CONTENT_MAX_LENGTH")
    # 单段最多反思次数
    max_reflections: int = Field(1, alias="MAX_REFLECTIONS")
    # 报告最大段落数
    max_paragraphs: int = Field(5, alias="MAX_PARAGRAPHS")
    # 单次搜索最大结果数（后续 TavilyToolset 内部还有一层去重裁剪）
    max_search_results: int = Field(12, alias="MAX_SEARCH_RESULTS")

    # ====== 输出控制 ======
    output_dir: Path = Field(default=Path("reports"), alias="OUTPUT_DIR")
    save_intermediate_state: bool = Field(
        default=True,
        validation_alias=AliasChoices("SAVE_INTERMEDIATE_STATE", "SAVE_INTERMEDIATE_STATES"),
    )

    def validate_required(self) -> None:
        """模仿你原来 Config.validate 的行为，缺啥就报错。"""
        missing = []
        if not self.llm_api_key:
            missing.append("QUERY_ENGINE_API_KEY")
        if not self.llm_model_name:
            missing.append("QUERY_ENGINE_MODEL_NAME")
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")

        if missing:
            msg = "配置缺失: " + ", ".join(missing)
            raise ValueError(msg)

        if not self.llm_provider and self.llm_model_name:
            self.llm_provider = self.llm_model_name


def load_settings() -> QueryEngineSettings:
    """对外暴露的加载函数，类似原来的 load_config。"""
    settings = QueryEngineSettings()  # 会自动从 env / .env 里读
    settings.validate_required()
    return settings


def print_settings(settings: QueryEngineSettings) -> None:
    print("\n=== Query Engine 配置 (LangChain 版) ===")
    print(f"LLM 模型: {settings.llm_model_name}")
    print(f"LLM Provider: {settings.llm_provider or '(未指定，默认为模型名)'}")
    print(f"LLM Base URL: {settings.llm_base_url or '(默认)'}")
    print(f"Tavily API Key: {'已配置' if settings.tavily_api_key else '未配置'}")
    print(f"搜索超时: {settings.search_timeout} 秒")
    print(f"最长内容长度: {settings.max_content_length}")
    print(f"最大反思次数: {settings.max_reflections}")
    print(f"最大段落数: {settings.max_paragraphs}")
    print(f"最大搜索结果数: {settings.max_search_results}")
    print(f"输出目录: {settings.output_dir}")
    print(f"保存中间状态: {settings.save_intermediate_state}")
    print(f"LLM API Key: {'已配置' if settings.llm_api_key else '未配置'}")
    print("======================================\n")


class QueryEngineConfig(QueryEngineSettings):
    """向后兼容的配置包装，适配代码里的属性命名。"""

    temperature: float = Field(0.2, alias="QUERY_ENGINE_TEMPERATURE")

    @property
    def llm_model(self) -> str:
        return self.llm_model_name

    @classmethod
    def from_env(cls) -> "QueryEngineConfig":
        cfg = cls()  # 会自动读取 env / .env
        cfg.validate_required()
        return cfg

    def validate(self) -> None:
        self.validate_required()
