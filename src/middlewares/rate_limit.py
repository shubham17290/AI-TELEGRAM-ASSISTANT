"""Rate limiting middleware for Telegram bot handlers."""

import time
from collections import defaultdict
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware:
    """
    Rate limiting middleware to prevent abuse.

    Limits the number of requests per user within a specified time period.
    """

    def __init__(
        self,
        rate_limit: Optional[int] = None,
        period: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum number of requests per period (defaults to config value)
            period: Time period in seconds (defaults to config value)
        """
        self.rate_limit = rate_limit or config.RATE_LIMIT
        self.period = period or config.RATE_LIMIT_PERIOD

        # Store request timestamps per user: {user_id: [timestamp1, timestamp2, ...]}
        self._requests: dict[int, list[float]] = defaultdict(list)

        logger.info(
            f"RateLimitMiddleware initialized - Limit: {self.rate_limit} requests "
            f"per {self.period} seconds"
        )

    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable
    ):
        """
        Check rate limit and process request.

        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in the chain

        Returns:
            Handler response or None if rate limited
        """
        if not update.effective_user:
            # If no user info, allow the request
            return await next_handler(update, context)

        user_id = update.effective_user.id
        current_time = time.time()

        # Clean old requests outside the time window
        self._requests[user_id] = [
            timestamp
            for timestamp in self._requests[user_id]
            if current_time - timestamp < self.period
        ]

        # Check if rate limit exceeded
        if len(self._requests[user_id]) >= self.rate_limit:
            logger.warning(
                f"Rate limit exceeded for user {user_id} - "
                f"{len(self._requests[user_id])} requests in {self.period}s"
            )

            # Send rate limit message to user
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"⚠️ Rate limit exceeded. Please try again in {self.period} seconds.",
                    parse_mode="Markdown",
                )

            return None

        # Add current request timestamp
        self._requests[user_id].append(current_time)

        # Process the request
        return await next_handler(update, context)

    def get_user_remaining_requests(self, user_id: int) -> int:
        """
        Get remaining requests for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of remaining requests
        """
        current_time = time.time()

        # Clean old requests
        self._requests[user_id] = [
            timestamp
            for timestamp in self._requests[user_id]
            if current_time - timestamp < self.period
        ]

        return max(0, self.rate_limit - len(self._requests[user_id]))

    def reset_user_limits(self, user_id: int) -> None:
        """
        Reset rate limits for a specific user.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self._requests:
            del self._requests[user_id]
            logger.info(f"Rate limits reset for user {user_id}")

    def clear_all_limits(self) -> None:
        """Clear all rate limit data."""
        self._requests.clear()
        logger.info("All rate limits cleared")
