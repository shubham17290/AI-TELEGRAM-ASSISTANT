"""Exception handling middleware for Telegram bot handlers.

In production mode, NEVER leaks stack traces or internal server details
to the user. All errors are logged internally with full details, and only
generic, user-friendly messages are sent to the client.
"""

import traceback
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import config
from src.database.connection import DatabaseTimeoutError
from src.services.ai_service import OpenAIServiceError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ExceptionHandlerMiddleware:
    """
    Global exception handling middleware.

    Catches and logs exceptions from handlers, preventing bot crashes.
    In production, error messages sent to the user NEVER contain stack
    traces or internal implementation details.
    """

    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable
    ):
        """
        Execute handler with exception handling.

        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in the chain

        Returns:
            Handler response or None if exception occurred
        """
        try:
            return await next_handler(update, context)

        except Exception as e:
            await self._handle_exception(update, context, e)
            return None

    async def _handle_exception(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, exception: Exception
    ) -> None:
        """
        Handle and log the exception.

        Logs the full exception details internally (with traceback), but
        sends only a generic message to the user.

        Args:
            update: Telegram update object
            context: Bot context
            exception: Exception that occurred
        """
        # Get user and chat info
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        chat_id = update.effective_chat.id if update.effective_chat else "Unknown"

        # Log the exception with full traceback (internal only)
        logger.error(
            f"Exception in handler - User: {user_id}, Chat: {chat_id}",
            exc_info=True,
        )

        # Send user-friendly error message (NEVER leak stack traces or details)
        try:
            if update.effective_chat:
                error_message = self._get_user_friendly_message(exception)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=error_message,
                    parse_mode="Markdown",
                )
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")

    def _get_user_friendly_message(self, exception: Exception) -> str:
        """
        Generate a user-friendly error message.

        In production, this always returns a generic message regardless of
        the exception type to avoid leaking internal information.

        Args:
            exception: Exception that occurred

        Returns:
            User-friendly error message (never contains stack trace or details)
        """
        if config.is_production:
            # Production: always return a generic message — no details leaked
            return (
                "❌ An unexpected error occurred. Our team has been notified. "
                "Please try again later."
            )

        # Development: provide slightly more context (but still no stack trace)
        error_type = type(exception).__name__

        # Custom exception types get user-friendly messages mapped by class,
        # not just by name, to avoid leaking internal implementation details.
        if isinstance(exception, DatabaseTimeoutError):
            return (
                "⏱️ The database is taking too long to respond. "
                "Please try again in a moment."
            )
        if isinstance(exception, OpenAIServiceError):
            return (
                "🤖 The AI service is currently unavailable. "
                "Please try again in a moment."
            )

        error_messages = {
            "ValueError": "❌ Invalid input provided. Please check your command.",
            "TypeError": "❌ Invalid command format. Please try again.",
            "KeyError": "❌ Requested resource not found.",
            "AttributeError": "❌ Something went wrong. Please try again later.",
            "ConnectionError": "❌ Connection error. Please try again later.",
            "TimeoutError": "⏱️ Request timed out. Please try again.",
        }

        return error_messages.get(
            error_type,
            "❌ An unexpected error occurred. Our team has been notified. Please try again later.",
        )
