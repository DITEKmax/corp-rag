from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the Python AI service foundation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Corp RAG AI Service", validation_alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")

    ai_database_url: str = Field(
        default="postgresql+asyncpg://corp_rag_ai:corp_rag_ai@localhost:5432/corp_rag_ai",
        validation_alias="AI_DB_URL",
    )
    rabbitmq_url: str = Field(
        default="amqp://corp_rag:corp_rag@localhost:5672/",
        validation_alias="RABBITMQ_URL",
    )
    amqp_consumers_enabled: bool = Field(
        default=False,
        validation_alias="AI_AMQP_CONSUMERS_ENABLED",
    )
    amqp_prefetch_count: int = Field(default=1, validation_alias="AI_AMQP_PREFETCH_COUNT")
    amqp_event_version: str = Field(default="1.0.0", validation_alias="AI_AMQP_EVENT_VERSION")
    amqp_source_service: str = Field(default="corp-rag-ai", validation_alias="AI_AMQP_SOURCE_SERVICE")
    qdrant_url: AnyHttpUrl = Field(
        default="http://localhost:6333",
        validation_alias="QDRANT_URL",
    )
    qdrant_initialize_collection: bool = Field(
        default=False,
        validation_alias="AI_QDRANT_INITIALIZE_COLLECTION",
    )
    embedding_model_name: str = Field(default="BAAI/bge-m3", validation_alias="AI_EMBEDDING_MODEL")
    embedding_batch_size: int = Field(default=32, validation_alias="AI_EMBEDDING_BATCH_SIZE")
    embedding_live_smoke_enabled: bool = Field(
        default=False,
        validation_alias="AI_EMBEDDING_LIVE_SMOKE_ENABLED",
    )
    embedding_model_cache_dir: str | None = Field(
        default=None,
        validation_alias="AI_EMBEDDING_MODEL_CACHE_DIR",
    )

    neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: SecretStr = Field(
        default="local-neo4j-password",
        validation_alias="NEO4J_PASSWORD",
    )
    neo4j_initialize_schema: bool = Field(
        default=False,
        validation_alias="AI_NEO4J_INITIALIZE_SCHEMA",
    )

    minio_endpoint: str = Field(default="localhost:9000", validation_alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(
        default="local-minio-access-key",
        validation_alias="MINIO_ACCESS_KEY",
    )
    minio_secret_key: SecretStr = Field(
        default="local-minio-secret-key",
        validation_alias="MINIO_SECRET_KEY",
    )
    minio_secure: bool = Field(default=False, validation_alias="MINIO_SECURE")
    minio_fetch_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="AI_MINIO_FETCH_TIMEOUT_SECONDS",
    )
    openrouter_api_key: SecretStr | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: AnyHttpUrl = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
    )
    deepseek_model_id: str = Field(
        default="deepseek/deepseek-v4-flash",
        validation_alias="DEEPSEEK_MODEL_ID",
    )

    langfuse_host: AnyHttpUrl = Field(
        default="http://localhost:3000",
        validation_alias="LANGFUSE_HOST",
    )
    langfuse_public_key: str = Field(
        default="local-langfuse-public-key",
        validation_alias="LANGFUSE_PUBLIC_KEY",
    )
    langfuse_secret_key: SecretStr = Field(
        default="local-langfuse-secret-key",
        validation_alias="LANGFUSE_SECRET_KEY",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
