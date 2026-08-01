"""Comprehensive security tests for Phase 10 — Security.

Covers:
1. Rate limiting & spam detection (warn-once behavior, 5 msg/min)
2. Secret validation startup check
3. Input sanitization (whitespace normalization, massive payloads)
4. API timeouts (AI service streaming, DB queries)
5. Error masking (no stack traces leaked to users)
6. Safe logging & data privacy (secret redaction on root logger)
7. Secure headers / TLS enforcement
"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes

from src.config.settings import Config, ConfigError, MissingRequiredVariableError
from src.database.connection import DatabaseTimeoutError
from src.middlewares.exception_handler import ExceptionHandlerMiddleware
from src.middlewares.rate_limit import RateLimitMiddleware
from src.middlewares.spam_detection import SpamDetectionMiddleware
from src.services.ai_service import OpenAIServiceError
from src.utils.logger import setup_logger
from src.utils.sanitizer import (
    sanitize_text,
    sanitize_command_argument,
    normalize_whitespace,
    is_payload_too_large,
    contains_malicious_patterns,
    escape_html,
    MAX_RAW_PAYLOAD_LENGTH,
)
from src.utils.secret_redactor import SecretRedactingFilter
from src.utils.secure_headers import (
    SECURITY_HEADERS,
    get_secure_http_client,
    get_secure_openai_client_kwargs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_update():
    """Create a mock Telegram update."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 123456789
    update.effective_user.username = "test_user"
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 123456789
    update.message = MagicMock(spec=Message)
    update.message.text = "Hello world"
    update.callback_query = None
    update.inline_query = None
    update.edited_message = None
    return update


@pytest.fixture
def mock_context():
    """Create a mock context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    return context


@pytest.fixture
def mock_handler():
    """Create a mock handler."""
    handler = AsyncMock()
    handler.return_value = "handler_result"
    return handler


# ---------------------------------------------------------------------------
# 1. Rate Limiting & Spam Detection
# ---------------------------------------------------------------------------

class TestRateLimitingSecurity:
    """Test rate limiting security features."""

    def test_default_rate_limit_is_5_per_minute(self):
        """Task requirement: max 5 messages per minute."""
        middleware = RateLimitMiddleware()
        assert middleware.rate_limit == 5
        assert middleware.period == 60

    @pytest.mark.asyncio
    async def test_warn_once_sends_single_warning(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that only ONE warning is sent per cooldown cycle."""
        middleware = RateLimitMiddleware(
            rate_limit=2, period=60, warn_once=True
        )

        # Fill up rate limit
        await middleware(mock_update, mock_context, mock_handler)
        await middleware(mock_update, mock_context, mock_handler)

        # First blocked request — should send a warning
        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None
        assert mock_context.bot.send_message.call_count == 1

        # Second blocked request — warning suppressed (silently ignored)
        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None
        assert mock_context.bot.send_message.call_count == 1  # Still only 1

        # Third blocked request — still suppressed
        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None
        assert mock_context.bot.send_message.call_count == 1  # Still only 1

    @pytest.mark.asyncio
    async def test_warn_once_disabled_sends_each_warning(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that warn-once disabled sends a warning per blocked request."""
        middleware = RateLimitMiddleware(
            rate_limit=2, period=60, warn_once=False
        )

        await middleware(mock_update, mock_context, mock_handler)
        await middleware(mock_update, mock_context, mock_handler)

        # First blocked request — warning sent
        await middleware(mock_update, mock_context, mock_handler)
        assert mock_context.bot.send_message.call_count == 1

        # Second blocked request — another warning
        await middleware(mock_update, mock_context, mock_handler)
        assert mock_context.bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_backoff_applied_on_rate_limit_exceeded(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that progressive backoff is applied."""
        middleware = RateLimitMiddleware(rate_limit=2, period=60)

        await middleware(mock_update, mock_context, mock_handler)
        await middleware(mock_update, mock_context, mock_handler)

        # Trigger rate limit
        await middleware(mock_update, mock_context, mock_handler)

        # Backoff should be applied
        assert mock_update.effective_user.id in middleware._backoff
        assert middleware._backoff[mock_update.effective_user.id]["violations"] == 1

    @pytest.mark.asyncio
    async def test_reset_user_limits(self, mock_update, mock_context, mock_handler):
        """Test resetting user limits clears warn flag."""
        middleware = RateLimitMiddleware(rate_limit=1, period=60, warn_once=True)

        await middleware(mock_update, mock_context, mock_handler)

        # Trigger block
        await middleware(mock_update, mock_context, mock_handler)
        assert middleware._warned.get(mock_update.effective_user.id, False) is True

        # Reset should clear warn flag
        middleware.reset_user_limits(mock_update.effective_user.id)
        assert mock_update.effective_user.id not in middleware._warned


class TestSpamDetectionSecurity:
    """Test spam detection security features."""

    def test_spam_detection_enabled_by_default(self):
        """Test that spam detection is enabled by default."""
        middleware = SpamDetectionMiddleware()
        assert middleware.enabled is True

    @pytest.mark.asyncio
    async def test_spam_detection_rejects_long_message(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that oversized messages are blocked."""
        middleware = SpamDetectionMiddleware(
            enabled=True, max_message_length=10
        )
        mock_update.message.text = "A" * 100

        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None
        assert mock_handler.call_count == 0

    @pytest.mark.asyncio
    async def test_spam_detection_ignores_disabled(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that disabled spam detection passes all requests."""
        middleware = SpamDetectionMiddleware(enabled=False)

        result = await middleware(mock_update, mock_context, mock_handler)
        assert result == "handler_result"


# ---------------------------------------------------------------------------
# 2. Secret Validation
# ---------------------------------------------------------------------------

class TestSecretValidation:
    """Test secret validation startup checks."""

    def test_required_secrets_present(self, monkeypatch):
        """Test that all required secrets are validated on Config creation."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
        monkeypatch.setenv("APP_ENV", "development")

        config = Config()
        assert config.TELEGRAM_BOT_TOKEN == "test_token_123456789"
        assert config.DATABASE_URL == "postgresql://user:pass@localhost/db"
        assert config.SECRET_KEY == "a" * 32

    def test_missing_telegram_token_raises(self, monkeypatch):
        """Test that missing TELEGRAM_BOT_TOKEN raises."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Config()

    def test_placeholder_secret_raises_startup_error(self, monkeypatch):
        """Test that placeholder secrets fail startup validation."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "your_telegram_bot_token_here")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "your_secret_key_here_change_in_production")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
        monkeypatch.setenv("APP_ENV", "development")

        config = Config()
        with pytest.raises(
            ConfigError, match="TELEGRAM_BOT_TOKEN appears to be a placeholder"
        ):
            config.validate_startup()

    def test_placeholder_secret_key_raises(self, monkeypatch):
        """Test that placeholder SECRET_KEY fails startup validation."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_123456789")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("SECRET_KEY", "your_secret_key_here_change_in_production")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
        monkeypatch.setenv("APP_ENV", "development")

        config = Config()
        with pytest.raises(ConfigError, match="SECRET_KEY appears to be a placeholder"):
            config.validate_startup()


# ---------------------------------------------------------------------------
# 3. Input Sanitization
# ---------------------------------------------------------------------------

class TestInputSanitization:
    """Test input sanitization security features."""

    def test_sanitize_strips_control_chars(self):
        """Test that control characters are stripped."""
        dirty = "Hello\x00\x01\x02World\x7f"
        clean = sanitize_text(dirty)
        assert clean == "HelloWorld"

    def test_sanitize_normalizes_unicode(self):
        """Test that Unicode is NFKC normalized."""
        # Full-width Latin characters (homoglyph attack)
        dirty = "\uff28ello"  # Ｈello (full-width H)
        clean = sanitize_text(dirty)
        assert clean == "Hello"

    def test_sanitize_truncates_long_text(self):
        """Test that text is truncated to safe length."""
        long_text = "A" * 10000
        clean = sanitize_text(long_text, max_length=100)
        assert len(clean) == 100

    def test_normalize_excessive_whitespace(self):
        """Test that massive whitespace runs are collapsed."""
        dirty = "hello" + " " * 100 + "world"
        clean = normalize_whitespace(dirty, max_consecutive=4)
        assert " " * 100 not in clean
        assert "hello world" == clean

    def test_is_payload_too_large(self):
        """Test massive payload rejection guard."""
        assert is_payload_too_large("A" * (MAX_RAW_PAYLOAD_LENGTH + 1)) is True
        assert is_payload_too_large("A" * 100) is False

    def test_sql_injection_detected(self):
        """Test that SQL injection patterns are detected."""
        assert contains_malicious_patterns("SELECT * FROM users; DROP TABLE users;")
        assert contains_malicious_patterns("'; DROP TABLE users; --")

    def test_sanitize_command_argument_strips_html(self):
        """Test that HTML tags are stripped from command args."""
        dirty = '<script>alert("xss")</script>'
        clean = sanitize_command_argument(dirty)
        assert "<script>" not in clean
        assert "alert" in clean

    def test_escape_html(self):
        """Test HTML escaping for XSS prevention."""
        escaped = escape_html('<script>alert("x")</script>')
        assert "<script>" not in escaped
        assert "<script>" in escaped
        assert ">" in escaped
        assert "alert" in escaped


# ---------------------------------------------------------------------------
# 4. API Timeouts
# ---------------------------------------------------------------------------

class TestAPITimeouts:
    """Test API timeouts security features."""

    def test_database_timeout_error_has_message(self):
        """Test that DatabaseTimeoutError has a clear message."""
        error = DatabaseTimeoutError(timeout=10, operation="test")
        assert "timed out after 10s" in str(error)
        assert error.timeout == 10

    @pytest.mark.asyncio
    async def test_database_session_has_timeout(self):
        """Test that get_session enforces a timeout (resolves config)."""
        from src.database.connection import get_session

        with pytest.raises(DatabaseTimeoutError):
            async with get_session(timeout=0.001) as _session:
                # Exceed the tiny timeout so the session scope must fail
                await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_ai_service_has_timeout_config(self):
        """Test that AI service timeout config exists."""
        from src.config.settings import config
        assert config.API_TIMEOUT >= 1
        assert config.DB_QUERY_TIMEOUT >= 1
        assert config.DB_POOL_TIMEOUT >= 1
        assert config.API_TIMEOUT <= 300  # Sanity cap


# ---------------------------------------------------------------------------
# 5. Error Masking
# ---------------------------------------------------------------------------

class TestErrorMasking:
    """Test error masking security features."""

    def test_production_always_returns_generic(self, monkeypatch):
        """Test that production NEVER leaks exception details."""
        # Patch the lazy config proxy used by the middleware so production
        # mode is active regardless of the process-wide test environment.
        monkeypatch.setattr(
            "src.middlewares.exception_handler.config.is_production",
            True,
            raising=False,
        )

        middleware = ExceptionHandlerMiddleware()
        message = middleware._get_user_friendly_message(
            ValueError("internal: root password = secret123")
        )

        # Must NOT contain the internal detail
        assert "root password" not in message
        assert "secret123" not in message
        assert "unexpected error" in message.lower()

    def test_development_still_masks_stack_trace(self):
        """Test that even in development, stack traces are never leaked."""
        middleware = ExceptionHandlerMiddleware()
        message = middleware._get_user_friendly_message(
            RuntimeError("Traceback (most recent call last): ...")
        )
        assert "Traceback" not in message
        assert "line " not in message

    @pytest.mark.asyncio
    async def test_exception_handler_masks_database_timeout(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that DatabaseTimeoutError gets a friendly message."""
        mock_handler.side_effect = DatabaseTimeoutError(timeout=10)
        middleware = ExceptionHandlerMiddleware()

        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None

        # Verify the message sent to the user
        sent_messages = [
            call.kwargs.get("text", "")
            for call in mock_context.bot.send_message.call_args_list
        ]
        assert len(sent_messages) == 1
        assert "database" in sent_messages[0].lower()
        assert "10s" not in sent_messages[0]

    @pytest.mark.asyncio
    async def test_exception_handler_masks_openai_error(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that OpenAIServiceError gets a friendly message."""
        mock_handler.side_effect = OpenAIServiceError("API key invalid")
        middleware = ExceptionHandlerMiddleware()

        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None

        sent_messages = [
            call.kwargs.get("text", "")
            for call in mock_context.bot.send_message.call_args_list
        ]
        assert len(sent_messages) == 1
        assert "API key invalid" not in sent_messages[0]


# ---------------------------------------------------------------------------
# 6. Safe Logging & Data Privacy
# ---------------------------------------------------------------------------

class TestSafeLogging:
    """Test safe logging and data privacy features."""

    def test_secret_redaction_filter_redacts_tokens(self):
        """Test that bot tokens are redacted from logs."""
        redactor = SecretRedactingFilter()
        text = "Bot token is 123456789:ABCdefGHIJklMNOpqrsTUVwxyz1234"
        redacted = redactor._redact_text(text)
        assert "123456789:ABCdef" not in redacted
        assert "[REDACTED]" in redacted

    def test_secret_redaction_filter_redacts_openai_keys(self):
        """Test that OpenAI API keys are redacted."""
        redactor = SecretRedactingFilter()
        text = "OpenAI key=sk-1234567890abcdefghijklmnopqrstuvwxyz123456"
        redacted = redactor._redact_text(text)
        assert "sk-1234567890" not in redacted
        assert "[REDACTED]" in redacted

    def test_secret_redaction_filter_redacts_passwords(self):
        """Test that passwords are redacted."""
        redactor = SecretRedactingFilter()
        text = "password=supersecret123 and api_key=mykey456"
        redacted = redactor._redact_text(text)
        assert "supersecret123" not in redacted
        assert "mykey456" not in redacted
        assert "[REDACTED]" in redacted

    def test_secret_redaction_filter_redacts_emails(self):
        """Test that emails are redacted when PII redaction is enabled."""
        redactor = SecretRedactingFilter(redact_pii=True)
        text = "contact me at user@example.com please"
        redacted = redactor._redact_text(text)
        assert "user@example.com" not in redacted
        assert "[REDACTED]" in redacted

    def test_known_secrets_redacted(self):
        """Test that known config secrets are redacted by exact match."""
        from src.config.settings import config as app_config

        redactor = SecretRedactingFilter()
        # Known secrets are loaded from config in _load_known_secrets
        known_secret = app_config.OPENAI_API_KEY
        assert known_secret  # sanity: config must expose a key in tests
        text = f"The secret token is {known_secret}"
        redacted = redactor._redact_text(text)
        assert known_secret not in redacted
        assert "[REDACTED]" in redacted

    def test_root_logger_has_redaction_filter(self):
        """Test that the root logger has the secret redaction filter."""
        setup_logger("test_redaction")
        root = logging.getLogger()
        assert any(
            isinstance(f, SecretRedactingFilter) for f in root.filters
        )

    def test_logger_uses_secret_redactor(self, caplog):
        """Test that a logger with redaction filter masks secrets in output."""
        setup_logger("test_module")
        test_logger = logging.getLogger("test_module")

        with caplog.at_level(logging.INFO):
            test_logger.info("Bot token: 123456789:ABCdefGHIJklMNOpqrsTUVwxyz1234")
            test_logger.info("Password: mypass123")

        for record in caplog.records:
            # The record's message could use %s formatting with args
            msg = record.getMessage()
            assert "123456789:ABCdef" not in msg
            assert "mypass123" not in msg


# ---------------------------------------------------------------------------
# 7. Secure Headers / TLS Enforcement
# ---------------------------------------------------------------------------

class TestSecureHeaders:
    """Test secure headers and TLS enforcement."""

    def test_security_headers_present(self):
        """Test that all key security headers are present."""
        assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"
        assert SECURITY_HEADERS["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in SECURITY_HEADERS
        assert "max-age=31536000" in SECURITY_HEADERS["Strict-Transport-Security"]
        assert "Content-Security-Policy" in SECURITY_HEADERS
        assert "no-store" in SECURITY_HEADERS["Cache-Control"]

    def test_secure_http_client_has_timeout(self):
        """Test that the secure HTTP client has a timeout configured."""
        import httpx
        client = get_secure_http_client(timeout=15)
        assert isinstance(client.timeout, httpx.Timeout)
        assert client.timeout.read == 15
        assert client.timeout.connect == 15

    def test_secure_http_client_tls_default(self):
        """Test that TLS verification is enabled by default."""
        client = get_secure_http_client()
        assert client._transport._pool._ssl_context is not None

    def test_secure_http_client_rejects_no_tls_in_production(self, monkeypatch):
        """Test that TLS verification cannot be disabled in production."""
        # Force production mode on the lazy config used by secure_headers
        monkeypatch.setattr(
            "src.utils.secure_headers.config.is_production",
            True,
            raising=False,
        )
        # secure_headers imports config lazily inside the function; patch the
        # settings module attribute that it will read.
        monkeypatch.setattr(
            "src.config.settings.config.is_production",
            True,
            raising=False,
        )

        with pytest.raises(
            ValueError, match="TLS certificate verification cannot be disabled"
        ):
            get_secure_http_client(verify_tls=False)

    def test_openai_client_kwargs_include_http_client(self):
        """Test that OpenAI client kwargs include a secure HTTP client."""
        kwargs = get_secure_openai_client_kwargs()
        assert "http_client" in kwargs
        assert kwargs["http_client"] is not None
