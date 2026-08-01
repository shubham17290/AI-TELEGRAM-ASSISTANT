"""Rate limiting middleware for Telegram bot handlers.

Provides multi-layer rate limiting:
- Standard rate limiting (max requests per period) — default: 5 messages per minute
- Burst detection (rapid requests in a short window)
- Progressive backoff (repeat offenders get longer cooldowns)
- Global rate limiting (across all users to prevent total system abuse)
- "Warn once" behavior: when a user is blocked, only ONE warning message is
  sent; all subsequent blocked requests are silently ignored until the
  cooldown expires.
"""

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

    Features:
    - Per-user standard rate limiting (configurable requests per period)
    - Burst detection (rapid requests in a short window)
    - Progressive backoff for repeat offenders
    - Global rate limiting (across all users)
    - "Warn once" per cooldown — only a single warning is sent to the user;
      subsequent blocked requests are silently dropped until the cooldown ends.
    """

    def __init__(
        self,
        rate_limit: Optional[int] = None,
        period: Optional[int] = None,
        burst_limit: Optional[int] = None,
        burst_period: Optional[int] = None,
        warn_once: Optional[bool] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum number of requests per period (defaults to config value, 5)
            period: Time period in seconds (defaults to config value, 60 = 1 minute)
            burst_limit: Max burst requests in short window (defaults to config value)
            burst_period: Burst window in seconds (defaults to config value)
            warn_once: If True, only send ONE warning per user per cooldown,
                then silently ignore blocked requests until the cooldown expires.
                (Defaults to config value `RATE_LIMIT_WARN_ONCE`.)
        """
        self.rate_limit = rate_limit or config.RATE_LIMIT
        self.period = period or config.RATE_LIMIT_PERIOD
        self.burst_limit = burst_limit or config.RATE_LIMIT_BURST
        self.burst_period = burst_period or config.RATE_LIMIT_BURST_PERIOD
        self.warn_once = warn_once if warn_once is not None else config.RATE_LIMIT_WARN_ONCE

        # Per-user request timestamps: {user_id: [timestamp1, ...]}
        self._requests: dict[int, list[float]] = defaultdict(list)

        # Progressive backoff tracking: {user_id: {'violations': int, 'blocked_until': float}}
        self._backoff: dict[int, dict] = {}

        # Tracks whether we already sent the single warning for the current
        # cooldown cycle: {user_id: bool}. Reset when the backoff expires.
        self._warned: dict[int, bool] = {}

        # Backoff configuration
        self._backoff_base_wait = 60  # 1 minute initial backoff
        self._backoff_max_wait = 3600  # 1 hour max backoff
        self._backoff_decay = 300  # 5 minutes after last violation, reset backoff

        # Global rate limiting
        self._global_requests: list[float] = []
        self._global_rate_limit = 500  # Max total requests per minute
        self._global_period = 60

        # Periodic cleanup interval
        self._last_cleanup_time = time.time()
        self._cleanup_interval = 300  # 5 minutes

        logger.info(
            f"RateLimitMiddleware initialized - "
            f"Limit: {self.rate_limit}/{self.period}s, "
            f"Burst: {self.burst_limit}/{self.burst_period}s, "
            f"Global: {self._global_rate_limit}/{self._global_period}s, "
            f"WarnOnce: {self.warn_once}"
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
            return await next_handler(update, context)

        user_id = update.effective_user.id
        current_time = time.time()

        # Periodic cleanup
        if current_time - self._last_cleanup_time > self._cleanup_interval:
            self._cleanup_old_data(current_time)
            self._last_cleanup_time = current_time

        # 1. Check progressive backoff
        if user_id in self._backoff:
            backoff_data = self._backoff[user_id]
            if current_time < backoff_data["blocked_until"]:
                remaining = int(backoff_data["blocked_until"] - current_time)
                logger.warning(
                    f"Rate limit backoff active for user {user_id} - "
                    f"blocked for {remaining}s (violation #{backoff_data['violations']})"
                )
                # Send ONLY ONE warning per cooldown cycle; ignore the rest silently.
                await self._send_warn_once_message(update, context, user_id, remaining)
                return None

            # Backoff expired — remove and reset warning flag
            del self._backoff[user_id]
            self._warned.pop(user_id, None)

        # 2. Clean old requests outside the standard window
        self._requests[user_id] = [
            ts
            for ts in self._requests[user_id]
            if current_time - ts < self.period
        ]

        # 3. Check standard rate limit
        if len(self._requests[user_id]) >= self.rate_limit:
            logger.warning(
                f"Rate limit exceeded for user {user_id} - "
                f"{len(self._requests[user_id])} requests in {self.period}s"
            )
            self._apply_backoff(user_id, current_time)
            await self._send_warn_once_message(update, context, user_id, self.period)
            return None

        # 4. Check burst limit (rapid requests in a short window)
        burst_count = sum(
            1 for ts in self._requests[user_id]
            if current_time - ts < self.burst_period
        )
        if burst_count >= self.burst_limit:
            logger.warning(
                f"Burst rate limit exceeded for user {user_id} - "
                f"{burst_count} requests in {self.burst_period}s"
            )
            self._apply_backoff(user_id, current_time)
            await self._send_warn_once_message(
                update, context, user_id, self.burst_period, burst=True
            )
            return None

        # 5. Check global rate limit (across all users)
        self._global_requests = [
            ts for ts in self._global_requests
            if current_time - ts < self._global_period
        ]
        if len(self._global_requests) >= self._global_rate_limit:
            logger.error(
                f"Global rate limit exceeded - "
                f"{len(self._global_requests)} requests in {self._global_period}s"
            )
            await self._send_rate_limit_message(update, context, 30, global_limit=True)
            return None

        # Add current request timestamp
        self._requests[user_id].append(current_time)
        self._global_requests.append(current_time)

        # Process the request
        return await next_handler(update, context)

    async def _send_warn_once_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        wait_time: int,
        burst: bool = False,
    ) -> None:
        """
        Send a rate-limit warning to the user only ONCE per cooldown cycle.

        When ``warn_once`` is enabled and the user is already blocked, this
        method suppresses repeated warnings so the user only sees a single
        polite notice until the cooldown expires.

        Args:
            update: Telegram update object
            context: Bot context
            user_id: Telegram user ID
            wait_time: Wait time in seconds
            burst: Whether this is a burst limit hit
        """
        # If warn-once is enabled and we already warned this user for the
        # current cooldown cycle, silently ignore the blocked request.
        if self.warn_once and self._warned.get(user_id, False):
            logger.debug(
                f"Rate limit warning suppressed for user {user_id} "
                f"(warn-once active for current cooldown)"
            )
            return

        # Mark that we sent the warning so subsequent blocked requests are silent
        self._warned[user_id] = True

        await self._send_rate_limit_message(update, context, wait_time, burst=burst)

    async def _send_rate_limit_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        wait_time: int,
        burst: bool = False,
        global_limit: bool = False,
    ) -> None:
        """
        Send a rate limit warning to the user.

        Args:
            update: Telegram update object
            context: Bot context
            wait_time: Wait time in seconds
            burst: Whether this is a burst limit hit
            global_limit: Whether this is a global limit hit
        """
        if global_limit:
            message = (
                "⚠️ The system is currently experiencing high load. "
                "Please try again in a moment."
            )
        elif burst:
            message = (
                f"⚠️ You are sending messages too quickly. "
                f"Please wait {wait_time} seconds between messages."
            )
        else:
            message = (
                f"⚠️ Rate limit exceeded. "
                f"Please try again in {wait_time} seconds."
            )

        try:
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message,
                )
        except Exception as e:
            logger.error(f"Failed to send rate limit message: {e}")

    def _apply_backoff(self, user_id: int, current_time: float) -> None:
        """
        Apply or escalate progressive backoff for a user.

        Args:
            user_id: Telegram user ID
            current_time: Current timestamp
        """
        if user_id in self._backoff:
            prev = self._backoff[user_id]
            violations = prev["violations"] + 1
            # Exponential backoff: 60s, 120s, 240s, 480s, ... capped at 3600s
            wait_time = min(
                self._backoff_base_wait * (2 ** (violations - 1)),
                self._backoff_max_wait,
            )
        else:
            violations = 1
            wait_time = self._backoff_base_wait

        self._backoff[user_id] = {
            "violations": violations,
            "blocked_until": current_time + wait_time,
        }

        logger.warning(
            f"Applied backoff for user {user_id} - "
            f"violation #{violations}, blocked for {wait_time}s"
        )

    def _cleanup_old_data(self, current_time: float) -> None:
        """
        Clean up old rate limit data.

        Args:
            current_time: Current timestamp
        """
        # Clean up expired backoff entries
        for user_id in list(self._backoff.keys()):
            if current_time > self._backoff[user_id]["blocked_until"] + self._backoff_decay:
                del self._backoff[user_id]
                self._warned.pop(user_id, None)

        # Clean up empty request lists
        for user_id in list(self._requests.keys()):
            self._requests[user_id] = [
                ts for ts in self._requests[user_id]
                if current_time - ts < self.period
            ]
            if not self._requests[user_id]:
                del self._requests[user_id]

        # Clean up global requests
        self._global_requests = [
            ts for ts in self._global_requests
            if current_time - ts < self._global_period
        ]

        logger.debug("Rate limit data cleanup completed")

    def get_user_remaining_requests(self, user_id: int) -> int:
        """
        Get remaining requests for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of remaining requests in the current window
        """
        current_time = time.time()

        self._requests[user_id] = [
            ts
            for ts in self._requests[user_id]
            if current_time - ts < self.period
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
        if user_id in self._backoff:
            del self._backoff[user_id]
        self._warned.pop(user_id, None)
        logger.info(f"Rate limits reset for user {user_id}")

    def clear_all_limits(self) -> None:
        """Clear all rate limit data."""
        self._requests.clear()
        self._backoff.clear()
        self._global_requests.clear()
        self._warned.clear()
        logger.info("All rate limits cleared")
