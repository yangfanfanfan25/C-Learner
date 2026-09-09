"""Runtime settings for the local PC backend."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_root() -> Path:
    """锚定数据目录到仓库根目录，避免受启动 CWD 影响。

    config.py 位于 apps/api/app/core/，parents[4] 即仓库根目录，
    数据目录固定为 <repo_root>/data（运行时数据与源码分离，不放在 apps/ 内）。
    """
    return Path(__file__).resolve().parents[4] / "data"


class Settings(BaseSettings):
    """Application settings loaded from defaults, environment variables, and .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "apps/api/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
        frozen=True,
    )

    service_name: str = Field(
        default="MY_RAG Local API",
        validation_alias=AliasChoices("MY_RAG_SERVICE_NAME", "SERVICE_NAME"),
    )
    storage_backend: str = Field(
        default="sqlite+milvus-lite",
        validation_alias=AliasChoices("MY_RAG_STORAGE_BACKEND", "STORAGE_BACKEND"),
    )
    data_root: Path = Field(
        default_factory=_default_data_root,
        validation_alias=AliasChoices("MY_RAG_DATA_ROOT", "DATA_ROOT"),
    )
    sqlite_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MY_RAG_SQLITE_PATH", "SQLITE_PATH"),
    )
    files_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MY_RAG_FILES_PATH", "FILES_PATH"),
    )
    milvus_lite_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MY_RAG_MILVUS_LITE_PATH", "MILVUS_LITE_PATH"),
    )
    milvus_collection_name: str = Field(
        default="knowledge_chunks",
        validation_alias=AliasChoices("MY_RAG_MILVUS_COLLECTION_NAME", "MILVUS_COLLECTION_NAME"),
    )
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_KEY", "EMBEDDING_KEY"),
    )
    embedding_api_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_BASE_URL", "EMBEDDING_BASE_URL"),
    )
    embedding_model_name: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        validation_alias=AliasChoices("EMBEDDING_MODEL_NAME", "EMBEDDING_MODEL"),
    )
    embedding_dimension: int = Field(
        default=512,
        ge=1,
        le=16384,
        validation_alias=AliasChoices("EMBEDDING_DIMENSION", "EMBEDDING_DIM"),
    )
    rag_top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        validation_alias=AliasChoices("MY_RAG_RAG_TOP_K", "RAG_TOP_K"),
    )
    document_queue_max_workers: int = Field(
        default=1,
        ge=1,
        le=8,
        description="文档处理队列后台 worker 数（当前为单会话，建议保持 1）",
        validation_alias=AliasChoices(
            "MY_RAG_DOCUMENT_QUEUE_MAX_WORKERS",
            "DOCUMENT_QUEUE_MAX_WORKERS",
        ),
    )
    document_llm_max_concurrency: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent chapter normalization calls for one document.",
        validation_alias=AliasChoices(
            "MY_RAG_DOCUMENT_LLM_MAX_CONCURRENCY",
            "DOCUMENT_LLM_MAX_CONCURRENCY",
        ),
    )
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_api_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        validation_alias="LLM_API_BASE_URL",
    )
    llm_model_name: str = Field(default="deepseek-chat", validation_alias="LLM_MODEL_NAME")
    llm_model_provider: str = Field(default="openai", validation_alias="LLM_MODEL_PROVIDER")
    langgraph_checkpoint_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "MY_RAG_LANGGRAPH_CHECKPOINT_PATH",
            "LANGGRAPH_CHECKPOINT_PATH",
        ),
    )
    zhipu_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ZHIPU_API_KEY", "ZHIPUAI_API_KEY"),
    )
    web_search_max_results: int = Field(
        default=5,
        ge=1,
        le=10,
        validation_alias="WEB_SEARCH_MAX_RESULTS",
    )
    web_search_timeout_seconds: int = Field(
        default=15,
        ge=3,
        le=60,
        validation_alias="WEB_SEARCH_TIMEOUT_SECONDS",
    )

    # -- 长期记忆（四层 L0-L3）：存储路径，逐层新增（见方案「配置逐层分配」表）--
    memory_root: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MY_RAG_MEMORY_ROOT", "MEMORY_ROOT"),
    )
    memory_conversations_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MY_RAG_MEMORY_CONVERSATIONS_PATH", "MEMORY_CONVERSATIONS_PATH"),
    )
    memory_records_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MY_RAG_MEMORY_RECORDS_PATH", "MEMORY_RECORDS_PATH"),
    )
    memory_profiles_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MY_RAG_MEMORY_PROFILES_PATH", "MEMORY_PROFILES_PATH"),
    )
    memory_milvus_l0_collection_name: str = Field(
        default="l0_messages",
        validation_alias=AliasChoices("MY_RAG_MEMORY_MILVUS_L0_COLLECTION", "MEMORY_MILVUS_L0_COLLECTION"),
    )
    memory_retention_days: int = Field(
        default=30,
        ge=1,
        validation_alias=AliasChoices("MY_RAG_MEMORY_RETENTION_DAYS", "MEMORY_RETENTION_DAYS"),
    )
    memory_milvus_l1_collection_name: str = Field(
        default="l1_memories",
        validation_alias=AliasChoices("MY_RAG_MEMORY_MILVUS_L1_COLLECTION", "MEMORY_MILVUS_L1_COLLECTION"),
    )
    memory_l1_every_n: int = Field(default=5, ge=1)
    memory_l1_batch_query: int = Field(default=20, ge=1)
    memory_l1_batch_process: int = Field(default=10, ge=1)
    memory_l1_idle_timeout_seconds: int = Field(default=600, ge=0)
    memory_l2_delay_after_l1_seconds: int = Field(default=10, ge=0)
    memory_l2_min_interval_seconds: int = Field(default=900, ge=0)
    memory_l2_max_interval_seconds: int = Field(default=3600, ge=0)
    memory_max_scenes: int = Field(default=15, ge=1)
    memory_l3_trigger_every_n: int = Field(default=50, ge=1)
    memory_recall_max_results: int = Field(default=5, ge=1)
    memory_recall_score_threshold: float = Field(default=0.5, ge=0.5, le=1.0)
    memory_recall_max_chars_per_memory: int = Field(default=500, ge=1)
    memory_recall_max_total_chars: int = Field(default=1500, ge=1)

    # -- 会话锚点记忆（短程 AnchorMemoryMiddleware）：默认启用，可显式关闭 --
    chat_anchor_memory_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("MY_RAG_CHAT_ANCHOR_MEMORY_ENABLED", "CHAT_ANCHOR_MEMORY_ENABLED"),
    )
    chat_anchor_every_n_turns: int = Field(default=10, ge=1)
    chat_anchor_min_new_tokens: int = Field(default=2000, ge=1)
    chat_anchor_max_anchor_chars: int = Field(default=2000, ge=100)

    @model_validator(mode="after")
    def fill_derived_paths(self) -> "Settings":
        data_root = self.data_root
        derived_paths = {
            "sqlite_path": data_root / "sqlite" / "my_rag.db",
            "milvus_lite_path": data_root / "milvus" / "knowledge.db",
            "files_path": data_root / "files",
            "langgraph_checkpoint_path": data_root / "sqlite" / "langgraph_checkpoints.sqlite",
        }
        for field_name, default_path in derived_paths.items():
            if getattr(self, field_name) is None:
                object.__setattr__(self, field_name, default_path)

        # 记忆根目录：先定 memory_root，再从它派生子目录
        if self.memory_root is None:
            object.__setattr__(self, "memory_root", data_root / "memory")
        memory_subpaths = {
            "memory_conversations_path": self.memory_root / "conversations",
            "memory_records_path": self.memory_root / "records",
            "memory_profiles_path": self.memory_root / "profiles",
        }
        for field_name, default_path in memory_subpaths.items():
            if getattr(self, field_name) is None:
                object.__setattr__(self, field_name, default_path)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
