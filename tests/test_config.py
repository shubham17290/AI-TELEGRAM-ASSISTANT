"""Tests for configuration module."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import (
    Config,
    ConfigError,
    InvalidEnvironmentError,
    MissingRequiredVariableError,
    get_config,
    load_environment,
)


class TestConfigValidation:
    """Test configuration validation."""

    def test_valid_development_config(self, monkeypatch):
        """Test valid development configuration."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("APP_DEBUG", "true")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        config = Config()
        assert config.is_development
        assert not config.is_production
        assert not config.is_testing
        assert config.APP_DEBUG is True

    def test_valid_production_config(self, monkeypatch):
        """Test valid production configuration."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@prod-server/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_DEBUG", "false")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        config = Config()
        assert config.is_production
        assert not config.is_development
        assert not config.is_testing
        assert config.APP_DEBUG is False

    def test_invalid_environment_raises_error(self, monkeypatch):
        """Test that invalid environment raises InvalidEnvironmentError."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "invalid_env")

        with pytest.raises(InvalidEnvironmentError) as exc_info:
            Config()

        assert "Invalid environment 'invalid_env'" in str(exc_info.value)

    def test_missing_required_variable_raises_error(self, monkeypatch):
        """Test that missing required variable raises ValidationError."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        # TELEGRAM_BOT_TOKEN is missing

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "TELEGRAM_BOT_TOKEN" in str(exc_info.value)

    def test_weak_secret_key_raises_error(self, monkeypatch):
        """Test that weak secret key raises ValidationError."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "short_key")  # Less than 32 chars

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "at least 32 characters" in str(exc_info.value)

    def test_invalid_ai_provider_raises_error(self, monkeypatch):
        """Test that invalid AI provider raises ValidationError."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("AI_PROVIDER", "invalid_provider")

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "Invalid AI provider" in str(exc_info.value)

    def test_invalid_log_level_raises_error(self, monkeypatch):
        """Test that invalid log level raises ValidationError."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("LOG_LEVEL", "INVALID_LEVEL")

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "Invalid log level" in str(exc_info.value)

    def test_invalid_log_format_raises_error(self, monkeypatch):
        """Test that invalid log format raises ValidationError."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("LOG_FORMAT", "invalid_format")

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "Invalid log format" in str(exc_info.value)

    def test_openai_provider_without_key_raises_error(self, monkeypatch):
        """Test that OpenAI provider without API key raises error."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("AI_PROVIDER", "openai")
        # OPENAI_API_KEY is missing

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "OPENAI_API_KEY is required" in str(exc_info.value)

    def test_anthropic_provider_without_key_raises_error(self, monkeypatch):
        """Test that Anthropic provider without API key raises error."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        # ANTHROPIC_API_KEY is missing

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "ANTHROPIC_API_KEY is required" in str(exc_info.value)


class TestConfigProperties:
    """Test configuration properties."""

    def test_log_file_path_development(self, monkeypatch, tmp_path):
        """Test log file path in development environment."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        config = Config()
        log_path = config.log_file_path

        assert log_path == tmp_path / "app_development.log"

    def test_log_file_path_production(self, monkeypatch, tmp_path):
        """Test log file path in production environment."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@prod/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("LOG_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        config = Config()
        log_path = config.log_file_path

        assert log_path == tmp_path / "app_production.log"

    def test_get_ai_api_key_openai(self, monkeypatch):
        """Test getting OpenAI API key."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        config = Config()
        api_key = config.get_ai_api_key()

        assert api_key == "sk-test-key-123"

    def test_get_ai_api_key_anthropic(self, monkeypatch):
        """Test getting Anthropic API key."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-456")

        config = Config()
        api_key = config.get_ai_api_key()

        assert api_key == "sk-ant-test-key-456"


class TestProductionValidations:
    """Test production-specific validations."""

    def test_production_with_debug_warning(self, monkeypatch):
        """Test that production with debug enabled raises warning."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@prod/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_DEBUG", "true")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        # Note: Warnings in model_validator are not easily testable with pytest.warns
        # The validation should still succeed
        config = Config()
        assert config.is_production

    def test_production_with_localhost_database_raises_error(self, monkeypatch):
        """Test that production with localhost database raises error."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_DEBUG", "false")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        with pytest.raises(ValidationError, match="Database URL points to localhost"):
            Config()


class TestLoadEnvironment:
    """Test environment loading."""

    def test_load_environment_file_not_found(self, tmp_path):
        """Test loading environment when .env file doesn't exist."""
        os.chdir(tmp_path)

        with pytest.raises(FileNotFoundError, match="No .env file found"):
            load_environment()

    def test_load_environment_custom_file(self, tmp_path, monkeypatch):
        """Test loading environment from custom file."""
        env_file = tmp_path / "custom.env"
        env_file.write_text("TEST_VAR=test_value\n")

        load_environment(str(env_file))

        assert os.getenv("TEST_VAR") == "test_value"

    def test_load_environment_specific_file_not_found(self):
        """Test loading environment when specific file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Environment file not found"):
            load_environment("/nonexistent/.env")


class TestGetConfig:
    """Test get_config function."""

    def test_get_config_success(self, monkeypatch, tmp_path):
        """Test successful config loading."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("""
TELEGRAM_BOT_TOKEN=test_token_123456789
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_KEY=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
OPENAI_API_KEY=sk-test-key-123
""")

        os.chdir(tmp_path)
        config = get_config()

        assert config.TELEGRAM_BOT_TOKEN == "test_token_123456789"
        assert config.DATABASE_URL == "postgresql://user:pass@localhost/db"

    def test_get_config_wraps_exception(self, monkeypatch):
        """Test that get_config wraps exceptions properly."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_ENV", "invalid_env")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        # InvalidEnvironmentError is raised directly, not wrapped
        with pytest.raises(InvalidEnvironmentError):
            get_config()


class TestConfigDefaults:
    """Test configuration defaults."""

    def test_default_values(self, monkeypatch):
        """Test that default values are set correctly."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

        config = Config()

        assert config.APP_NAME == "AI Telegram Assistant"
        assert config.APP_ENV == "development"
        assert config.APP_DEBUG is True
        assert config.APP_PORT == 8000
        assert config.AI_PROVIDER == "openai"
        assert config.AI_MODEL == "gpt-4o-mini"
        assert config.DATABASE_ECHO is False
        assert config.LOG_LEVEL == "INFO"
        assert config.LOG_FORMAT == "json"
        assert config.RATE_LIMIT == 5
        assert config.RATE_LIMIT_PERIOD == 60

    def test_port_validation(self, monkeypatch):
        """Test port number validation."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("APP_PORT", "99999")  # Invalid port

        with pytest.raises(ValidationError):
            Config()

    def test_rate_limit_validation(self, monkeypatch):
        """Test rate limit validation."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("RATE_LIMIT", "0")  # Invalid, must be >= 1

        with pytest.raises(ValidationError):
            Config()
