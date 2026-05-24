from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    llm_provider: str = Field(default="dashscope_compatible", validation_alias=AliasChoices("LLM_PROVIDER"))
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "QUERY_ENGINE_API_KEY", "DASHSCOPE_API_KEY"),
    )
    openai_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "QUERY_ENGINE_BASE_URL"),
    )
    openai_model: str = Field(
        default="qwen-plus",
        validation_alias=AliasChoices("OPENAI_MODEL", "QUERY_ENGINE_MODEL_NAME"),
    )
    tavily_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("TAVILY_API_KEY"),
    )
    redis_url: str = Field(default="", validation_alias=AliasChoices("REDIS_URL"))
    max_retries: int = Field(default=3, validation_alias=AliasChoices("MAX_RETRIES"))
    tavily_max_results: int = Field(default=5, validation_alias=AliasChoices("TAVILY_MAX_RESULTS"))
    enable_node_perf: bool = Field(default=False, validation_alias=AliasChoices("ENABLE_NODE_PERF"))
    enable_cache: bool = Field(default=False, validation_alias=AliasChoices("ENABLE_CACHE"))
    cache_db_path: str = Field(default="var/cache/langgraph_cache.sqlite", validation_alias=AliasChoices("CACHE_DB_PATH"))
    enable_rag: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_RAG"))
    rag_database_url: str = Field(default="postgresql://localhost:5432/bettafish", validation_alias=AliasChoices("RAG_DATABASE_URL"))
    rag_top_k: int = Field(default=4, validation_alias=AliasChoices("RAG_TOP_K"))
    enable_rag_writeback: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_RAG_WRITEBACK"))
    rag_writeback_quality_threshold: int = Field(default=70, validation_alias=AliasChoices("RAG_WRITEBACK_QUALITY_THRESHOLD"))
    rag_dense_weight: float = Field(default=0.7, validation_alias=AliasChoices("RAG_DENSE_WEIGHT"))
    rag_sparse_weight: float = Field(default=0.3, validation_alias=AliasChoices("RAG_SPARSE_WEIGHT"))
    rag_trust_bonus: float = Field(default=0.5, validation_alias=AliasChoices("RAG_TRUST_BONUS"))
    embedding_provider: str = Field(default="siliconflow", validation_alias=AliasChoices("EMBEDDING_PROVIDER"))
    embedding_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("EMBEDDING_API_KEY"))
    embedding_model: str = Field(default="BAAI/bge-m3", validation_alias=AliasChoices("EMBEDDING_MODEL"))
    embedding_dim: int = Field(default=1024, validation_alias=AliasChoices("EMBEDDING_DIM"))
    enable_reranker: bool = Field(default=False, validation_alias=AliasChoices("ENABLE_RERANKER"))
    enable_conversation_memory: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_CONVERSATION_MEMORY"))
    enable_ltm: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_LTM"))
    # LTM pgvector (defaults to same DB as RAG)
    ltm_database_url: str = Field(default="", validation_alias=AliasChoices("LTM_DATABASE_URL"))
    # Memory thresholds (v2.0 time-driven decay)
    stale_importance: float = Field(default=0.2, validation_alias=AliasChoices("STALE_IMPORTANCE"))
    soft_delete_importance: float = Field(default=0.1, validation_alias=AliasChoices("SOFT_DELETE_IMPORTANCE"))
    hard_delete_days_after_soft: int = Field(default=30, validation_alias=AliasChoices("HARD_DELETE_DAYS_AFTER_SOFT"))
    refresh_max_retries: int = Field(default=3, validation_alias=AliasChoices("REFRESH_MAX_RETRIES"))
    refresh_failed_penalty: float = Field(default=0.5, validation_alias=AliasChoices("REFRESH_FAILED_PENALTY"))
    # Phase 2: Agent/Tool config
    enable_legitimacy_scorer: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_LEGITIMACY_SCORER"))
    enable_archetype_detector: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_ARCHETYPE_DETECTOR"))
    report_temperature: float = Field(default=0.5, validation_alias=AliasChoices("REPORT_TEMPERATURE"))
    analysis_temperature: float = Field(default=0.3, validation_alias=AliasChoices("ANALYSIS_TEMPERATURE"))
    enable_report_self_review: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_REPORT_SELF_REVIEW"))
    enable_report_llm_self_review: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_REPORT_LLM_SELF_REVIEW"))
    search_cache_ttl: int = Field(default=600, validation_alias=AliasChoices("SEARCH_CACHE_TTL"))
    enable_otel: bool = Field(default=False, validation_alias=AliasChoices("ENABLE_OTEL", "OTEL_ENABLED"))
    otel_exporter: str = Field(default="none", validation_alias=AliasChoices("OTEL_EXPORTER"))
    otel_endpoint: str = Field(default="", validation_alias=AliasChoices("OTEL_ENDPOINT"))
    otel_service_name: str = Field(default="bettafish-harness", validation_alias=AliasChoices("OTEL_SERVICE_NAME"))
    prometheus_enabled: bool = Field(default=False, validation_alias=AliasChoices("PROMETHEUS_ENABLED"))
    alerting_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALERTING_ENABLED"))
    deployment_env: str = Field(default="local", validation_alias=AliasChoices("DEPLOYMENT_ENV"))
    authn: str = Field(default="none", validation_alias=AliasChoices("AUTHN"))
    authz_model: str = Field(default="none", validation_alias=AliasChoices("AUTHZ_MODEL"))
    monthly_budget: float = Field(default=100.0, validation_alias=AliasChoices("MONTHLY_BUDGET"))
    cost_per_run_cap: float = Field(default=1.0, validation_alias=AliasChoices("COST_PER_RUN_CAP"))
    owner: str = Field(default="<Zayn>", validation_alias=AliasChoices("OWNER"))
    team_size: int = Field(default=1, validation_alias=AliasChoices("TEAM_SIZE"))
    roles: str = Field(default="builder", validation_alias=AliasChoices("ROLES"))
    enable_guardrails: bool = Field(default=False, validation_alias=AliasChoices("ENABLE_GUARDRAILS"))
    guardrails_mode: str = Field(default="minimal_blocking", validation_alias=AliasChoices("GUARDRAILS_MODE"))
    enable_query_store: bool = Field(default=False, validation_alias=AliasChoices("ENABLE_QUERY_STORE"))
    query_store_path: str = Field(
        default="logs/harness/query_store.sqlite",
        validation_alias=AliasChoices("QUERY_STORE_PATH"),
    )
    experiment_id: str = Field(default="", validation_alias=AliasChoices("EXPERIMENT_ID"))
    experiment_rollout_pct: int = Field(default=0, validation_alias=AliasChoices("EXPERIMENT_ROLLOUT_PCT"))
    experiment_variants: str = Field(
        default="control,treatment",
        validation_alias=AliasChoices("EXPERIMENT_VARIANTS"),
    )
    force_variant: str = Field(default="", validation_alias=AliasChoices("FORCE_VARIANT"))

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
