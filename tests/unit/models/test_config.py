"""Unit tests for configuration models (AppConfig, DatabaseConfig, LLMConfig).

Tests Pydantic validation rules, environment variable loading, and default values
per data-model.md specifications.

Constitutional Requirements:
- All variables must have explicit type annotations
- All functions must have return type annotations
- Thread-based testing only (no async/await)
- mypy --strict compliant
- pylint 10.00/10.00 compliant
"""

from typing import Any

from pydantic import ValidationError
import pytest

# These imports will fail initially - that's expected for TDD RED phase
from backend.src.models.config import AppConfig, DatabaseConfig, LLMConfig


@pytest.mark.unit
class TestDatabaseConfig:
    """Test DatabaseConfig model validation and defaults."""

    def test_database_config_with_required_fields(self) -> None:
        """Test DatabaseConfig creation with all required fields."""
        config: DatabaseConfig = DatabaseConfig(
            user="testuser",
            password="testpass",
        )

        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "ragcsv"
        assert config.user == "testuser"
        assert config.password == "testpass"
        assert config.pool_min_size == 2
        assert config.pool_max_size == 10
        assert config.statement_timeout == 30000

    def test_database_config_with_custom_values(self) -> None:
        """Test DatabaseConfig with overridden defaults."""
        config: DatabaseConfig = DatabaseConfig(
            host="db.example.com",
            port=5433,
            database="custom_db",
            user="admin",
            password="secret",
            pool_min_size=5,
            pool_max_size=20,
            statement_timeout=60000,
        )

        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.database == "custom_db"
        assert config.pool_min_size == 5
        assert config.pool_max_size == 20
        assert config.statement_timeout == 60000

    def test_database_config_missing_required_fields(self) -> None:
        """Test DatabaseConfig fails without required user/password."""
        with pytest.raises(ValidationError) as exc_info:
            DatabaseConfig()  # type: ignore[call-arg]

        errors: list[dict[str, Any]] = exc_info.value.errors()
        error_fields: set[str] = {error["loc"][0] for error in errors}

        assert "user" in error_fields
        assert "password" in error_fields

    def test_database_config_invalid_port(self) -> None:
        """Test DatabaseConfig rejects invalid port numbers."""
        with pytest.raises(ValidationError):
            DatabaseConfig(
                user="testuser",
                password="testpass",
                port=-1,  # Invalid port
            )

        with pytest.raises(ValidationError):
            DatabaseConfig(
                user="testuser",
                password="testpass",
                port=70000,  # Port out of range
            )

    def test_database_config_env_prefix(self) -> None:
        """Test DatabaseConfig uses DB_ environment variable prefix."""
        # This test verifies the model_config.env_prefix setting
        config: DatabaseConfig = DatabaseConfig(
            user="envuser",
            password="envpass",
        )

        # Verify env_prefix is set correctly
        assert config.model_config.get("env_prefix") == "DB_"


@pytest.mark.unit
class TestLLMConfig:
    """Test LLMConfig model validation and defaults."""

    def test_llm_config_defaults(self) -> None:
        """Test LLMConfig default values."""
        config: LLMConfig = LLMConfig()

        assert config.provider == "openai"
        assert config.api_key is None
        assert config.model == "gpt-4"
        assert config.embedding_model == "text-embedding-3-small"
        assert config.max_tokens == 4096
        assert config.temperature == 0.1

    def test_llm_config_with_custom_values(self) -> None:
        """Test LLMConfig with overridden values."""
        config: LLMConfig = LLMConfig(
            provider="anthropic",
            api_key="sk-test-123",
            model="claude-opus-4-5-20251101",
            embedding_model="custom-embedding",
            max_tokens=8192,
            temperature=0.7,
        )

        assert config.provider == "anthropic"
        assert config.api_key == "sk-test-123"
        assert config.model == "claude-opus-4-5-20251101"
        assert config.embedding_model == "custom-embedding"
        assert config.max_tokens == 8192
        assert config.temperature == 0.7

    def test_llm_config_temperature_validation(self) -> None:
        """Test LLMConfig temperature must be between 0.0 and 2.0."""
        # Valid temperatures
        config_low: LLMConfig = LLMConfig(temperature=0.0)
        assert config_low.temperature == 0.0

        config_high: LLMConfig = LLMConfig(temperature=2.0)
        assert config_high.temperature == 2.0

        # Invalid temperatures
        with pytest.raises(ValidationError):
            LLMConfig(temperature=-0.1)

        with pytest.raises(ValidationError):
            LLMConfig(temperature=2.1)

    def test_llm_config_env_prefix(self) -> None:
        """Test LLMConfig uses LLM_ environment variable prefix."""
        config: LLMConfig = LLMConfig()

        # Verify env_prefix is set correctly
        assert config.model_config.get("env_prefix") == "LLM_"


@pytest.mark.unit
class TestAppConfig:
    """Test AppConfig model validation and composition."""

    def test_app_config_defaults(self) -> None:
        """Test AppConfig loads from .env file correctly."""
        # Note: This loads from .env file if present
        config: AppConfig = AppConfig(db=DatabaseConfig(user="testuser", password="testpass"))

        assert config.log_level == "INFO"
        # CORS origins loaded from .env file (not default)
        assert isinstance(config.cors_origins, list)
        assert len(config.cors_origins) > 0
        assert config.query_timeout_seconds == 30
        assert config.max_file_size_bytes == 0  # Unlimited

        # Verify nested database config
        assert config.db.host == "localhost"
        assert config.db.port == 5432

    def test_app_config_with_custom_values(self) -> None:
        """Test AppConfig with custom values."""
        db_config: DatabaseConfig = DatabaseConfig(
            user="produser",
            password="prodpass",
            host="prod.db.com",
        )

        llm_config: LLMConfig = LLMConfig(
            provider="anthropic",
            api_key="sk-prod-key",
        )

        config: AppConfig = AppConfig(
            db=db_config,
            llm=llm_config,
            log_level="DEBUG",
            cors_origins=["https://example.com", "https://app.example.com"],
            query_timeout_seconds=60,
            max_file_size_bytes=1000000000,  # 1GB
        )

        assert config.log_level == "DEBUG"
        assert len(config.cors_origins) == 2
        assert config.query_timeout_seconds == 60
        assert config.max_file_size_bytes == 1000000000

        # Verify nested configs
        assert config.db.host == "prod.db.com"
        assert config.llm.provider == "anthropic"

    def test_app_config_query_timeout_validation(self) -> None:
        """Test AppConfig query timeout must be positive."""
        with pytest.raises(ValidationError):
            AppConfig(
                db=DatabaseConfig(user="test", password="test"),
                query_timeout_seconds=-1,  # Invalid negative timeout
            )

    def test_app_config_max_file_size_validation(self) -> None:
        """Test AppConfig max file size must be non-negative."""
        # Test: Zero value means unlimited file size
        config_unlimited: AppConfig = AppConfig(
            db=DatabaseConfig(user="test", password="test"),
            max_file_size_bytes=0,
        )
        assert config_unlimited.max_file_size_bytes == 0

        # Positive values are valid
        config_limited: AppConfig = AppConfig(
            db=DatabaseConfig(user="test", password="test"),
            max_file_size_bytes=1000,
        )
        assert config_limited.max_file_size_bytes == 1000

        # Negative should fail
        with pytest.raises(ValidationError):
            AppConfig(
                db=DatabaseConfig(user="test", password="test"),
                max_file_size_bytes=-1,
            )

    def test_app_config_env_file_loading(self) -> None:
        """Test AppConfig uses .env file for configuration."""
        config: AppConfig = AppConfig(db=DatabaseConfig(user="test", password="test"))

        # Verify env_file is set correctly
        assert config.model_config.get("env_file") == ".env"
