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
    ADMIN_TELEGRAM_ID: Optional[int] = Field(default=None, description="Telegram user ID of the admin")

    # Rate Limiting
    # Task requirement: max 5 messages per minute
    RATE_LIMIT: int = Field(default=5, ge=1, description="Rate limit per period (default 5 messages)")
    RATE_LIMIT_PERIOD: int = Field(default=60, ge=1, description="Rate limit period in seconds (default 60s = 1 minute)")
    RATE_LIMIT_BURST: int = Field(default=3, ge=1, description="Max burst requests in short window")
    RATE_LIMIT_BURST_PERIOD: int = Field(default=3, ge=1, description="Burst window in seconds")
    # When a user is blocked by rate limiting, only send ONE warning message; ignore the rest silently.
    RATE_LIMIT_WARN_ONCE: bool = Field(
        default=True,
        description="Send only one rate-limit warning to a user, then silently ignore until cooldown expires",
    )

    # Spam Detection
    SPAM_DETECTION_ENABLED: bool = Field(default=True, description="Enable spam detection middleware")
    SPAM_MAX_DUPLICATES: int = Field(default=3, ge=1, description="Max duplicate messages before flagging")
    SPAM_DUPLICATE_WINDOW: int = Field(default=60, ge=1, description="Duplicate detection window in seconds")
    SPAM_MAX_URLS: int = Field(default=3, ge=0, description="Max URLs per message before flagging")
    SPAM_MAX_MESSAGE_LENGTH: int = Field(default=4096, ge=1, description="Max message length in characters")

    # Timeouts (in seconds)
    API_TIMEOUT: int = Field(default=30, ge=1, le=300, description="Timeout for external API calls")
    DB_QUERY_TIMEOUT: int = Field(default=10, ge=1, le=60, description="Timeout for database queries")
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1, description="Database connection pool timeout")

    # Secure Logging
    LOG_REDACT_SECRETS: bool = Field(default=True, description="Redact secrets from log output")
    LOG_REDACT_PII: bool = Field(default=True, description="Redact PII from log output")

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

    def validate_startup(self) -> list[str]:
        """
        Perform strict validation of all required secrets and settings on startup.

        This method goes beyond pydantic field validators to check for:
        - Placeholder/default secret values that must be changed
        - Production-specific security requirements
        - Cross-dependency validation

        Returns:
            List of warning messages (non-fatal issues found).

        Raises:
            ConfigError: If any critical validation fails.
        """
        warnings: list[str] = []
        errors: list[str] = []

        # --- Check for placeholder/default secret values ---
        placeholder_patterns = [
            "your_secret_key_here",
            "your_telegram_bot_token_here",
            "your_openai_api_key_here",
            "your_anthropic_api_key_here",
            "change_in_production",
            "changeme",
            "example",
            "placeholder",
        ]

        def _is_placeholder(value: Optional[str]) -> bool:
            if not value:
                return False
            lower_val = value.lower()
            return any(p in lower_val for p in placeholder_patterns)

        if _is_placeholder(self.TELEGRAM_BOT_TOKEN):
            errors.append("TELEGRAM_BOT_TOKEN appears to be a placeholder. Set a real token.")

        if _is_placeholder(self.SECRET_KEY):
            errors.append("SECRET_KEY appears to be a placeholder. Set a real secret key.")

        if self.OPENAI_API_KEY and _is_placeholder(self.OPENAI_API_KEY):
            errors.append("OPENAI_API_KEY appears to be a placeholder.")

        if self.ANTHROPIC_API_KEY and _is_placeholder(self.ANTHROPIC_API_KEY):
            errors.append("ANTHROPIC_API_KEY appears to be a placeholder.")

        # --- Production-specific strict checks ---
        if self.is_production:
            # APP_DEBUG must be False in production
            if self.APP_DEBUG:
                errors.append("APP_DEBUG must be False in production environment.")

            # SECRET_KEY must not be a common weak value
            weak_keys = {"secret", "key", "mysecret", "test", "default"}
            if self.SECRET_KEY.lower() in weak_keys:
                errors.append("SECRET_KEY is too weak for production.")

            # ADMIN_TELEGRAM_ID should be set in production
            if self.ADMIN_TELEGRAM_ID is None:
                warnings.append(
                    "ADMIN_TELEGRAM_ID is not set. Admin commands will be disabled in production."
                )

            # LOG_LEVEL should not be DEBUG in production
            if self.LOG_LEVEL.upper() == "DEBUG":
                warnings.append(
                    "LOG_LEVEL is DEBUG in production. Consider using INFO or higher."
                )

            # DATABASE_ECHO should be False in production
            if self.DATABASE_ECHO:
                warnings.append(
                    "DATABASE_ECHO is enabled in production. SQL queries will be logged."
                )

        # --- Raise on critical errors ---
        if errors:
            error_msg = "Startup validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ConfigError(error_msg)

        return warnings


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
