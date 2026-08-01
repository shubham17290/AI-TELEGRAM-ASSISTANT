"""Tests for middleware implementations."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes

from src.middlewares.auth import AuthMiddleware
from src.middlewares.exception_handler import ExceptionHandlerMiddleware
from src.middlewares.logging import LoggingMiddleware
from src.middlewares.rate_limit import RateLimitMiddleware
from src.middlewares.registry import get_registry
from src.middlewares.spam_detection import SpamDetectionMiddleware
from src.middlewares.user_activity import UserActivityMiddleware


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
    update.message.text = "/start"
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


class TestLoggingMiddleware:
    """Test logging middleware."""

    @pytest.mark.asyncio
    async def test_logging_middleware_success(self, mock_update, mock_context, mock_handler):
        """Test successful handler execution with logging."""
        middleware = LoggingMiddleware()
        result = await middleware(mock_update, mock_context, mock_handler)

        assert result == "handler_result"
        mock_handler.assert_called_once_with(mock_update, mock_context)

    @pytest.mark.asyncio
    async def test_logging_middleware_exception(self, mock_update, mock_context, mock_handler):
        """Test logging middleware with exception."""
        mock_handler.side_effect = Exception("Test error")
        middleware = LoggingMiddleware()

        with pytest.raises(Exception):
            await middleware(mock_update, mock_context, mock_handler)

    @pytest.mark.asyncio
    async def test_get_update_type_message_text(self, mock_update):
        """Test update type detection for text message."""
        middleware = LoggingMiddleware()
        update_type = middleware._get_update_type(mock_update)
        assert update_type == "message/text"

    @pytest.mark.asyncio
    async def test_get_update_type_callback(self, mock_update):
        """Test update type detection for callback query."""
        mock_update.message = None
        mock_update.callback_query = MagicMock()
        middleware = LoggingMiddleware()
        update_type = middleware._get_update_type(mock_update)
        assert update_type == "callback_query"


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_request(self, mock_update, mock_context, mock_handler):
        """Test that rate limiter allows requests under limit."""
        middleware = RateLimitMiddleware(rate_limit=3, period=60)
        result = await middleware(mock_update, mock_context, mock_handler)

        assert result == "handler_result"
        mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_excess(self, mock_update, mock_context, mock_handler):
        """Test that rate limiter blocks requests over limit."""
        middleware = RateLimitMiddleware(rate_limit=2, period=60)

        # Make requests up to limit
        await middleware(mock_update, mock_context, mock_handler)
        await middleware(mock_update, mock_context, mock_handler)

        # This request should be blocked
        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None
        assert mock_handler.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_reset(self, mock_update, mock_context, mock_handler):
        """Test rate limit reset functionality."""
        middleware = RateLimitMiddleware(rate_limit=2, period=1)

        # Fill up rate limit
        await middleware(mock_update, mock_context, mock_handler)
        await middleware(mock_update, mock_context, mock_handler)

        # Wait for period to expire
        time.sleep(1.1)

        # Should allow request again
        result = await middleware(mock_update, mock_context, mock_handler)
        assert result == "handler_result"

    def test_get_user_remaining_requests(self):
        """Test getting remaining requests for a user."""
        middleware = RateLimitMiddleware(rate_limit=5, period=60)
        user_id = 123456789

        # Initially should have all requests available
        assert middleware.get_user_remaining_requests(user_id) == 5


class TestExceptionHandlerMiddleware:
    """Test exception handling middleware."""

    @pytest.mark.asyncio
    async def test_exception_handler_success(self, mock_update, mock_context, mock_handler):
        """Test successful handler execution."""
        middleware = ExceptionHandlerMiddleware()
        result = await middleware(mock_update, mock_context, mock_handler)

        assert result == "handler_result"

    @pytest.mark.asyncio
    async def test_exception_handler_catches_exception(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that exception handler catches and logs exceptions."""
        mock_handler.side_effect = ValueError("Test error")
        middleware = ExceptionHandlerMiddleware()

        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_friendly_message_value_error(self):
        """Test user-friendly message for ValueError."""
        middleware = ExceptionHandlerMiddleware()
        message = middleware._get_user_friendly_message(ValueError("test"))
        assert "Invalid input" in message

    @pytest.mark.asyncio
    async def test_get_user_friendly_message_unknown_error(self):
        """Test user-friendly message for unknown error."""
        middleware = ExceptionHandlerMiddleware()
        message = middleware._get_user_friendly_message(Exception("unknown"))
        assert "unexpected error" in message


class TestUserActivityMiddleware:
    """Test user activity middleware."""

    @pytest.mark.asyncio
    async def test_user_activity_tracking(self, mock_update, mock_context, mock_handler):
        """Test that user activity is tracked."""
        middleware = UserActivityMiddleware()
        result = await middleware(mock_update, mock_context, mock_handler)

        assert result == "handler_result"

        # Check that activity was recorded
        stats = middleware.get_user_stats(123456789)
        assert stats is not None
        assert stats["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_user_activity_history(self, mock_update, mock_context, mock_handler):
        """Test user activity history."""
        middleware = UserActivityMiddleware()

        # Make multiple requests
        await middleware(mock_update, mock_context, mock_handler)
        await middleware(mock_update, mock_context, mock_handler)

        # Check history
        activity = middleware.get_user_activity(123456789)
        assert len(activity) == 2

    def test_get_active_users(self):
        """Test getting active users."""
        middleware = UserActivityMiddleware()
        current_time = time.time()

        # No active users initially
        assert middleware.get_active_users(current_time) == []


class TestAuthMiddleware:
    """Test authentication middleware."""

    @pytest.mark.asyncio
    async def test_auth_disabled_allows_all(self, mock_update, mock_context, mock_handler):
        """Test that disabled auth allows all requests."""
        middleware = AuthMiddleware(enabled=False)
        result = await middleware(mock_update, mock_context, mock_handler)

        assert result == "handler_result"

    @pytest.mark.asyncio
    async def test_auth_enabled_blocks_unauthorized(
        self, mock_update, mock_context, mock_handler
    ):
        """Test that enabled auth blocks unauthorized users."""
        middleware = AuthMiddleware(enabled=True)
        result = await middleware(mock_update, mock_context, mock_handler)

        assert result is None

    @pytest.mark.asyncio
    async def test_auth_allows_authorized(self, mock_update, mock_context, mock_handler):
        """Test that auth allows authorized users."""
        middleware = AuthMiddleware(enabled=True)
        middleware.authorize_user(123456789)

        result = await middleware(mock_update, mock_context, mock_handler)
        assert result == "handler_result"

    @pytest.mark.asyncio
    async def test_auth_blocks_banned(self, mock_update, mock_context, mock_handler):
        """Test that auth blocks banned users."""
        middleware = AuthMiddleware(enabled=True)
        middleware.authorize_user(123456789)
        middleware.ban_user(123456789, "Test ban")

        result = await middleware(mock_update, mock_context, mock_handler)
        assert result is None

    def test_is_authorized(self):
        """Test authorization check."""
        middleware = AuthMiddleware(enabled=True)
        middleware.authorize_user(123)

        assert middleware.is_authorized(123) is True
        assert middleware.is_authorized(456) is False

    def test_is_banned(self):
        """Test ban check."""
        middleware = AuthMiddleware(enabled=True)
        middleware.ban_user(123, "Test")

        assert middleware.is_banned(123) is True
        assert middleware.is_banned(456) is False


class TestMiddlewareRegistry:
    """Test middleware registry."""

    def test_get_registry_singleton(self):
        """Test that registry is a singleton."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_registry_initialize(self):
        """Test registry initialization."""
        registry = get_registry()
        registry.initialize()

        all_middlewares = registry.get_all()
        assert len(all_middlewares) == 6
        assert "logging" in all_middlewares
        assert "rate_limit" in all_middlewares
        assert "exception_handler" in all_middlewares
        assert "user_activity" in all_middlewares
        assert "auth" in all_middlewares
        assert "spam_detection" in all_middlewares

    def test_get_middleware(self):
        """Test getting middleware by name."""
        registry = get_registry()
        middleware = registry.get("logging")

        assert middleware is not None
        assert isinstance(middleware, LoggingMiddleware)

    def test_get_nonexistent_middleware(self):
        """Test getting non-existent middleware."""
        registry = get_registry()
        middleware = registry.get("nonexistent")

        assert middleware is None

    def test_get_default_chain(self):
        """Test getting default middleware chain."""
        registry = get_registry()
        chain = registry.get_default_chain()

        assert len(chain) == 6
        assert isinstance(chain[0], ExceptionHandlerMiddleware)
        assert isinstance(chain[1], AuthMiddleware)
        assert isinstance(chain[2], SpamDetectionMiddleware)
        assert isinstance(chain[3], RateLimitMiddleware)
        assert isinstance(chain[4], UserActivityMiddleware)
        assert isinstance(chain[5], LoggingMiddleware)
