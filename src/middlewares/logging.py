"""Logging middleware for Telegram bot handlers."""

import logging
import time
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from src.utils.logger import get_logger


logger = get_logger(__name__)


class LoggingMiddleware:
    """Logging middleware for bot handlers with performance tracking."""

    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable
    ):
        """
        Log incoming updates and handler execution.

        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in the chain

        Returns:
            Handler response
        """
        # Log incoming update
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        chat_id = update.effective_chat.id if update.effective_chat else "Unknown"
        update_type = self._get_update_type(update)

        logger.info(
            f"Incoming update - Type: {update_type}, "
            f"User: {user_id}, Chat: {chat_id}"
        )

        # Track handler execution time
        start_time = time.time()
        try:
            result = await next_handler(update, context)
            execution_time = time.time() - start_time

            logger.info(
                f"Handler completed - Type: {update_type}, "
                f"User: {user_id}, Time: {execution_time:.3f}s"
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Handler failed - Type: {update_type}, "
                f"User: {user_id}, Error: {str(e)}, Time: {execution_time:.3f}s",
                exc_info=True,
            )
            raise

    def _get_update_type(self, update: Update) -> str:
        """Determine the type of update."""
        if update.message:
            if update.message.text:
                return "message/text"
            elif update.message.photo:
                return "message/photo"
            elif update.message.document:
                return "message/document"
            elif update.message.voice:
                return "message/voice"
            else:
                return "message/other"
        elif update.callback_query:
            return "callback_query"
        elif update.inline_query:
            return "inline_query"
        elif update.edited_message:
            return "edited_message"
        else:
            return "unknown"
