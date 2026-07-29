"""Authentication placeholder middleware for Telegram bot handlers."""

import logging
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AuthMiddleware:
    """
    Authentication placeholder middleware.

    This is a placeholder for future authentication implementation.
    Currently allows all requests but logs authentication attempts.
    """

    def __init__(self, enabled: bool = False):
        """
        Initialize authentication middleware.

        Args:
            enabled: Whether authentication is enabled (default: False for placeholder)
        """
        self.enabled = enabled

        # Placeholder for authorized users: {user_id: user_data}
        self._authorized_users: dict[int, dict] = {}

        # Placeholder for banned users: {user_id: reason}
        self._banned_users: dict[int, str] = {}

        logger.info(
            f"AuthMiddleware initialized - Enabled: {enabled} (placeholder mode)"
        )

    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable
    ):
        """
        Check authentication and process request.

        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in the chain

        Returns:
            Handler response or None if not authenticated
        """
        # If authentication is disabled, allow all requests
        if not self.enabled:
            return await next_handler(update, context)

        # Placeholder authentication logic
        if not update.effective_user:
            logger.warning("Request without user information")
            return None

        user_id = update.effective_user.id

        # Check if user is banned
        if user_id in self._banned_users:
            logger.warning(f"Blocked request from banned user {user_id}")
            await self._send_message(
                update,
                context,
                "🚫 You are banned from using this bot.",
            )
            return None

        # Check if user is authorized
        if user_id not in self._authorized_users:
            logger.info(f"Unauthorized request from user {user_id}")
            await self._send_message(
                update,
                context,
                "🔒 Authentication required. This feature is not yet implemented.",
            )
            return None

        # User is authorized, process the request
        logger.debug(f"Authenticated request from user {user_id}")
        return await next_handler(update, context)

    async def _send_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        """
        Send a message to the user.

        Args:
            update: Telegram update object
            context: Bot context
            text: Message text
        """
        try:
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def authorize_user(self, user_id: int, user_data: Optional[dict] = None) -> None:
        """
        Authorize a user (placeholder method).

        Args:
            user_id: Telegram user ID
            user_data: Optional user data dictionary
        """
        self._authorized_users[user_id] = user_data or {}
        logger.info(f"User {user_id} authorized")

    def ban_user(self, user_id: int, reason: str = "No reason provided") -> None:
        """
        Ban a user (placeholder method).

        Args:
            user_id: Telegram user ID
            reason: Reason for banning
        """
        self._banned_users[user_id] = reason
        logger.warning(f"User {user_id} banned: {reason}")

    def unban_user(self, user_id: int) -> None:
        """
        Unban a user (placeholder method).

        Args:
            user_id: Telegram user ID
        """
        if user_id in self._banned_users:
            del self._banned_users[user_id]
            logger.info(f"User {user_id} unbanned")

    def revoke_user_authorization(self, user_id: int) -> None:
        """
        Revoke user authorization (placeholder method).

        Args:
            user_id: Telegram user ID
        """
        if user_id in self._authorized_users:
            del self._authorized_users[user_id]
            logger.info(f"Authorization revoked for user {user_id}")

    def is_authorized(self, user_id: int) -> bool:
        """
        Check if a user is authorized.

        Args:
            user_id: Telegram user ID

        Returns:
            True if authorized, False otherwise
        """
        return user_id in self._authorized_users

    def is_banned(self, user_id: int) -> bool:
        """
        Check if a user is banned.

        Args:
            user_id: Telegram user ID

        Returns:
            True if banned, False otherwise
        """
        return user_id in self._banned_users

    def get_authorized_users(self) -> list[int]:
        """
        Get list of authorized user IDs.

        Returns:
            List of authorized user IDs
        """
        return list(self._authorized_users.keys())

    def get_banned_users(self) -> list[int]:
        """
        Get list of banned user IDs.

        Returns:
            List of banned user IDs
        """
        return list(self._banned_users.keys())
