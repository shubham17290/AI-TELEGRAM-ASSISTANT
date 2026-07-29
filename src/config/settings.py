"""Application configuration settings with validation and environment loading."""

import os
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv, find_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass


class MissingRequiredVariableError(ConfigError):
    """Raised when a required environment variable is missing."""

    def __init__(self, variable_name: str, message: Optional[str] = None):
        self.variable_name = variable_name
        if message is None:
            message = f"Required environment variable '{variable_name}' is not set."
        super().__init__(message)


class InvalidEnvironmentError(ConfigError):
    """Raised when an invalid environment is specified."""

    def __init__(self, environment: str, valid_environments: list[str]):
        message = (
            f"Invalid environment '{environment}'. "
            f"Must be one of: {', '.join(valid_environments)}"
        )
        super().__init__(message)


class Config(BaseSettings):
    """
    Application configuration with validation.

    Loads environment variables from .env file and validates required fields.
    Separates development and production configurations.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        validate_default=True,
    )

    # Application
    APP_NAME: str = "AI Telegram Assistant"
    APP_ENV: str = Field(default="development", description="Application environment")
    APP_DEBUG: bool = Field(default=True, description="Enable debug mode")
    APP_PORT: int = Field(default=8000, ge=1, le=65535, description="Application port")

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(description="Telegram bot token from @BotFather")

    # AI/LLM Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")
    AI_PROVIDER: str = Field(default="openai", description="AI provider (openai/anthropic)")
    AI_MODEL: str = Field(default="gpt-4o-mini", description="AI model to use")

    # Database
    DATABASE_URL: str = Field(description="Database connection URL")
    DATABASE_ECHO: bool = Field(default=False, description="Enable SQL query logging")

    # Redis (optional, for caching)
    REDIS_URL: Optional[str] = Field(default=None, description="Redis connection URL")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format (json/text)")
    LOG_DIR: str = Field(default="logs", description="Log directory")
    LOG_MAX_BYTES: int = Field(default=10485760, description="Max log file size in bytes (10MB)")
    LOG_BACKUP_COUNT: int = Field(default=5, description="Number of backup log files to keep")

    # Security
    SECRET_KEY: str = Field(description="Secret key for session encryption")

    # Rate Limiting
    RATE_LIMIT: int = Field(default=30, ge=1, description="Rate limit per period")
    RATE_LIMIT_PERIOD: int = Field(default=60, ge=1, description="Rate limit period in seconds")

    # Environment-specific configurations
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.APP_ENV == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.APP_ENV == "testing"

    @property
    def database_connection_string(self) -> str:
        """Get database connection string with proper formatting."""
        return self.DATABASE_URL

    @property
    def log_file_path(self) -> Path:
        """Get log file path based on environment."""
        return Path(self.LOG_DIR) / f"app_{self.APP_ENV}.log"

    @field_validator("APP_ENV")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate that APP_ENV is one of the allowed values."""
        valid_environments = ["development", "production", "testing"]
        if v not in valid_environments:
            raise InvalidEnvironmentError(v, valid_environments)
        return v

    @field_validator("AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        """Validate AI provider."""
        valid_providers = ["openai", "anthropic"]
        if v not in valid_providers:
            raise ValueError(
                f"Invalid AI provider '{v}'. Must be one of: {', '.join(valid_providers)}"
            )
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(valid_levels)}"
            )
        return v_upper

    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["json", "text"]
        if v not in valid_formats:
            raise ValueError(
                f"Invalid log format '{v}'. Must be one of: {', '.join(valid_formats)}"
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key strength."""
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long for security."
            )
        return v

    @model_validator(mode="after")
    def validate_ai_configuration(self) -> "Config":
        """Validate AI configuration based on provider."""
        if self.AI_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is required when AI_PROVIDER is 'openai'"
            )
        if self.AI_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when AI_PROVIDER is 'anthropic'"
            )

        # Production-specific validations
        if self.is_production:
            if self.APP_DEBUG:
                import warnings
                warnings.warn(
                    "APP_DEBUG is enabled in production environment. "
                    "This is not recommended for security reasons.",
                    RuntimeWarning
                )

            if "localhost" in self.DATABASE_URL or "127.0.0.1" in self.DATABASE_URL:
                raise ValueError(
                    "Database URL points to localhost in production environment. "
                    "Please use a production database."
                )

        return self

    def get_ai_api_key(self) -> str:
        """
        Get the appropriate API key based on the AI provider.

        Returns:
            API key for the configured provider

        Raises:
            ValueError: If the API key is not configured
        """
        if self.AI_PROVIDER == "openai":
            if not self.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
            return self.OPENAI_API_KEY
        elif self.AI_PROVIDER == "anthropic":
            if not self.ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key not configured")
            return self.ANTHROPIC_API_KEY
        else:
            raise ValueError(f"Unsupported AI provider: {self.AI_PROVIDER}")


def load_environment(env_file: Optional[str] = None) -> None:
    """
    Load environment variables from .env file.

    Args:
        env_file: Optional path to .env file. If not provided, searches for .env file.

    Raises:
        FileNotFoundError: If .env file is not found
    """
    if env_file:
        env_path = Path(env_file)
        if not env_path.exists():
            raise FileNotFoundError(f"Environment file not found: {env_file}")
        load_dotenv(env_file, override=True)
    else:
        # Search for .env file in current directory and parent directories
        dotenv_path = find_dotenv(usecwd=True)
        if not dotenv_path:
            raise FileNotFoundError(
                "No .env file found. Please create a .env file based on .env.example"
            )
        load_dotenv(dotenv_path, override=True)


def get_config() -> Config:
    """
    Load and validate configuration.

    Returns:
        Validated Config instance

    Raises:
        ConfigError: If configuration is invalid
        FileNotFoundError: If .env file is not found
    """
    try:
        # Load environment variables
        load_environment()

        # Create and validate config (validations are now in the Config class)
        config = Config()

        return config

    except Exception as e:
        # Re-raise with more context
        if isinstance(e, ConfigError):
            raise
        raise ConfigError(f"Failed to load configuration: {str(e)}") from e


# Global config instance (lazy loading)
_config_instance: Optional[Config] = None


def get_or_create_config() -> Config:
    """
    Get or create the global config instance.

    Returns:
        Config instance

    Raises:
        ConfigError: If configuration is invalid
        FileNotFoundError: If .env file is not found
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = get_config()
    return _config_instance


# For backward compatibility, create a lazy config proxy
class _LazyConfig:
    """Lazy config proxy that loads config on first access."""

    def __getattr__(self, name: str) -> Any:
        if '_config' not in self.__dict__:
            self._config = get_or_create_config()
        return getattr(self._config, name)

    def __call__(self) -> Config:
        """Allow calling config() to get the actual Config instance."""
        if '_config' not in self.__dict__:
            self._config = get_or_create_config()
        return self._config


# Create lazy config instance
config = _LazyConfig()
