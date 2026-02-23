"""Configuration models for RAG CSV Crew application.

Defines Pydantic models for application configuration including database,
LLM, and app-level settings. All models support environment variable loading.

Constitutional Requirements:
- All variables have explicit type annotations
- All functions have return type annotations
- Thread-based operations only (no async/await)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """PostgreSQL database configuration.

    Loads from environment variables with DB_ prefix.
    Supports connection pooling and statement timeouts per FR-023.

    Attributes:
        host: Database server hostname
        port: Database server port (1-65535)
        database: Database name
        user: Database username (required)
        password: Database password (required)
        pool_min_size: Minimum connection pool size
        pool_max_size: Maximum connection pool size
        statement_timeout: Query timeout in milliseconds
    """

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = "ragcsv"
    user: str
    password: str
    pool_min_size: int = Field(default=2, ge=1)
    pool_max_size: int = Field(default=10, ge=1)
    statement_timeout: int = Field(default=30000, ge=0)  # 30 seconds in ms

    model_config = SettingsConfigDict(env_prefix="DATABASE_", env_file=".env", extra="ignore")


class LLMConfig(BaseSettings):
    """LLM API configuration for text generation and embeddings.

    Supports multiple providers (OpenAI, Anthropic) with configurable
    models and parameters per FR-005, FR-006, FR-007.

    Attributes:
        provider: LLM provider name (openai, anthropic, ollama)
        api_key: API key for LLM provider (optional for local models)
        model: Text generation model name
        embedding_model: Embedding model name for semantic search
        max_tokens: Maximum tokens in LLM response
        temperature: Sampling temperature (0.0-2.0)
    """

    provider: str = "openai"
    api_key: str | None = None
    model: str = "gpt-4"
    embedding_model: str = "text-embedding-3-small"
    max_tokens: int = Field(default=4096, ge=1)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")


class AppConfig(BaseSettings):
    """Application-level configuration.

    Composes database and LLM configurations with app-specific settings.
    Loads from .env file if present per constitution requirements.

    Attributes:
        db: Database configuration
        llm: LLM configuration
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        cors_origins: Allowed CORS origins for web interface
        query_timeout_seconds: Maximum query execution time
        max_file_size_bytes: Maximum CSV upload size (0 = unlimited)
    """

    db: DatabaseConfig = Field(default_factory=DatabaseConfig)  # type: ignore[arg-type]
    llm: LLMConfig = Field(default_factory=LLMConfig)
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    query_timeout_seconds: int = Field(default=30, ge=1)
    max_file_size_bytes: int = Field(default=0, ge=0)  # 0 = unlimited

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str] | Any:
        """Parse comma-separated CORS origins from environment variable.

        Handles both string (comma-separated) and list formats.
        Validates that wildcard (*) is not used for security.

        Args:
            value: Raw value from environment variable or direct assignment

        Returns:
            List of CORS origin strings

        Raises:
            ValueError: If wildcard (*) origin is specified (security violation)

        Examples:
            "http://localhost:3000,http://localhost:5173" -> ["http://localhost:3000", "http://localhost:5173"]  # pylint: disable=line-too-long
            ["http://localhost:3000"] -> ["http://localhost:3000"]

        Security (T210-POLISH):
            - Wildcard "*" origins are rejected to prevent CORS bypass
            - All origins must be explicit fully-qualified URLs
        """
        origins: list[str]

        if isinstance(value, str):
            # Split comma-separated string and strip whitespace
            origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        elif isinstance(value, list):
            origins = value
        else:
            return value

        # Security validation: Reject wildcard origins (T210-POLISH)
        for origin in origins:
            if origin == "*":
                raise ValueError(
                    "Wildcard '*' CORS origin is not allowed for security reasons. "
                    "Please specify explicit origins (e.g., 'http://localhost:5173')."
                )

        return origins
