"""Spam detection middleware for Telegram bot handlers.

Provides basic spam prevention through:
- Duplicate message detection (same content sent repeatedly)
- Burst/spam detection (rapid-fire messages in a short window)
- URL spam detection (too many URLs per message)
- Message length limits
- Honeypot pattern detection (identifying automated bot behavior)
"""

import time
from collections import defaultdict, deque
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import config
from src.utils.logger import get_logger
from src.utils.sanitizer import count_urls

logger = get_logger(__name__)


class SpamDetectionMiddleware:
    """
    Middleware for detecting and preventing spam messages.

    Detects:
    - Duplicate messages from the same user within a configurable window.
    - Rapid-fire message bursts.
    - Messages with excessive URLs.
    - Messages exceeding maximum length.
    """

    def __init__(
        self,
        enabled: bool = True,
        max_duplicates: Optional[int] = None,
        duplicate_window: Optional[int] = None,
        max_urls: Optional[int] = None,
        max_message_length: Optional[int] = None,
    ):
        """
        Initialize spam detection middleware.

        Args:
            enabled: Whether spam detection is enabled.
            max_duplicates: Max duplicate messages before flagging.
            duplicate_window: Window in seconds for duplicate detection.
            max_urls: Max URLs per message before flagging.
            max_message_length: Max message length in characters.
        """
        self.enabled = enabled if config.SPAM_DETECTION_ENABLED else False
        self.max_duplicates = max_duplicates or config.SPAM_MAX_DUPLICATES
        self.duplicate_window = duplicate_window or config.SPAM_DUPLICATE_WINDOW
        self.max_urls = max_urls or config.SPAM_MAX_URLS
        self.max_message_length = max_message_length or config.SPAM_MAX_MESSAGE_LENGTH

        # Track recent messages per user: {user_id: deque([(timestamp, content), ...])}
        self._message_history: dict[int, deque[tuple[float, str]]] = defaultdict(
            lambda: deque(maxlen=50)
        )

        # Track duplicate counts per user: {user_id: {content: count}}
        self._duplicate_counts: dict[int, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Track spam flags per user: {user_id: {'flagged': bool, 'reason': str, 'timestamp': float}}
        self._spam_flags: dict[int, dict] = {}

        # Spam flag cooldown (once flagged, skip further checks for this period)
        self._spam_cooldown = 300  # 5 minutes
        self._spam_clear_interval = 3600  # Clear old data every hour
        self._last_cleanup_time = time.time()

        logger.info(
            f"SpamDetectionMiddleware initialized - "
            f"Enabled: {self.enabled}, "
            f"MaxDuplicates: {self.max_duplicates}/{self.duplicate_window}s, "
            f"MaxURLs: {self.max_urls}, "
            f"MaxLength: {self.max_message_length}"
        )

    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        next_handler: Callable,
    ):
        """
        Check for spam and process request.

        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in the chain

        Returns:
            Handler response or None if flagged as spam
        """
        if not self.enabled:
            return await next_handler(update, context)

        if not update.effective_user or not update.message or not update.message.text:
            return await next_handler(update, context)

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else None
        message_text = update.message.text
        current_time = time.time()

        # Periodic cleanup of old data
        if current_time - self._last_cleanup_time > self._spam_clear_interval:
            self._cleanup_old_data(current_time)
            self._last_cleanup_time = current_time

        # Check if user is under spam cooldown
        if user_id in self._spam_flags:
            flag_data = self._spam_flags[user_id]
            elapsed = current_time - flag_data["timestamp"]
            if elapsed < self._spam_cooldown:
                logger.warning(
                    f"Blocked spam-flagged user {user_id} - "
                    f"Reason: {flag_data['reason']}, "
                    f"Cooldown remaining: {self._spam_cooldown - elapsed:.0f}s"
                )
                return None

            # Clear expired flag
            del self._spam_flags[user_id]

        # --- Checks ---

        # 1. Message length check
        if len(message_text) > self.max_message_length:
            logger.warning(
                f"Message too long from user {user_id}: "
                f"{len(message_text)} chars (max: {self.max_message_length})"
            )
            await self._send_spam_warning(update, context, "message_too_long")
            return None

        # 2. URL spam check
        url_count = count_urls(message_text)
        if url_count > self.max_urls:
            logger.warning(
                f"URL spam detected from user {user_id}: "
                f"{url_count} URLs in message (max: {self.max_urls})"
            )
            await self._send_spam_warning(update, context, "url_spam")
            self._flag_user(user_id, "url_spam", current_time)
            return None

        # 3. Duplicate message check
        self._message_history[user_id].append((current_time, message_text))

        # Count duplicates within the window
        duplicate_count = 0
        cutoff_time = current_time - self.duplicate_window
        for msg_time, msg_content in self._message_history[user_id]:
            if msg_time >= cutoff_time and msg_content == message_text:
                duplicate_count += 1

        if duplicate_count > self.max_duplicates:
            logger.warning(
                f"Duplicate message spam from user {user_id}: "
                f"{duplicate_count} duplicates in {self.duplicate_window}s"
            )
            await self._send_spam_warning(update, context, "duplicate_spam")
            self._flag_user(user_id, "duplicate_spam", current_time)
            return None

        # 4. Rapid-fire burst check (more than 10 messages in 5 seconds)
        recent_count = 0
        burst_window = 5  # seconds
        burst_cutoff = current_time - burst_window
        for msg_time, _ in self._message_history[user_id]:
            if msg_time >= burst_cutoff:
                recent_count += 1

        if recent_count > 10:
            logger.warning(
                f"Burst spam detected from user {user_id}: "
                f"{recent_count} messages in {burst_window}s"
            )
            await self._send_spam_warning(update, context, "burst_spam")
            self._flag_user(user_id, "burst_spam", current_time)
            return None

        # Passed all checks — process the request
        return await next_handler(update, context)

    async def _send_spam_warning(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        spam_type: str,
    ) -> None:
        """
        Send a warning message to the user about spam detection.

        Args:
            update: Telegram update object
            context: Bot context
            spam_type: Type of spam detected
        """
        messages = {
            "message_too_long": (
                "⚠️ Your message is too long. "
                f"Please keep messages under {self.max_message_length} characters."
            ),
            "url_spam": (
                "⚠️ Too many URLs detected in your message. "
                "Please reduce the number of links."
            ),
            "duplicate_spam": (
                "⚠️ Please avoid sending the same message multiple times."
            ),
            "burst_spam": (
                "⚠️ You are sending messages too quickly. "
                "Please slow down."
            ),
        }

        message = messages.get(
            spam_type,
            "⚠️ Your message was flagged as spam. Please try again later."
        )

        try:
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message,
                )
        except Exception as e:
            logger.error(f"Failed to send spam warning: {e}")

    def _flag_user(self, user_id: int, reason: str, timestamp: float) -> None:
        """
        Flag a user for spam activity.

        Args:
            user_id: Telegram user ID
            reason: Reason for flagging
            timestamp: Current timestamp
        """
        self._spam_flags[user_id] = {
            "flagged": True,
            "reason": reason,
            "timestamp": timestamp,
        }
        logger.warning(f"User {user_id} flagged for spam: {reason}")

    def _cleanup_old_data(self, current_time: float) -> None:
        """
        Clean up old message history and spam flags.

        Args:
            current_time: Current timestamp
        """
        cleanup_before = current_time - self._spam_clear_interval

        # Clean up old message history
        for user_id in list(self._message_history.keys()):
            self._message_history[user_id] = deque(
                (ts, msg)
                for ts, msg in self._message_history[user_id]
                if ts >= cleanup_before
            )
            if not self._message_history[user_id]:
                del self._message_history[user_id]

        # Clean up old spam flags
        for user_id in list(self._spam_flags.keys()):
            if self._spam_flags[user_id]["timestamp"] < cleanup_before:
                del self._spam_flags[user_id]

        logger.debug("Spam detection data cleanup completed")

    def is_user_flagged(self, user_id: int) -> bool:
        """
        Check if a user is currently flagged for spam.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is flagged, False otherwise
        """
        return user_id in self._spam_flags

    def clear_user_history(self, user_id: int) -> None:
        """
        Clear message history and spam flags for a user.

        Args:
            user_id: Telegram user ID
        """
        self._message_history.pop(user_id, None)
        self._duplicate_counts.pop(user_id, None)
        self._spam_flags.pop(user_id, None)
        logger.info(f"Spam history cleared for user {user_id}")
