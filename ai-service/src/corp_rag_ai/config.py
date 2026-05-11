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
    qdrant_url: AnyHttpUrl = Field(
        default="http://localhost:6333",
        validation_alias="QDRANT_URL",
    )

    neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: SecretStr = Field(
        default="local-neo4j-password",
        validation_alias="NEO4J_PASSWORD",
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
