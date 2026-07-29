"""User activity logging middleware for Telegram bot handlers."""

import time
from datetime import datetime
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.utils.logger import get_logger

logger = get_logger(__name__)


class UserActivityMiddleware:
    """
    User activity tracking middleware.

    Logs user interactions and maintains activity statistics.
    """

    def __init__(self, max_history_size: int = 1000):
        """
        Initialize user activity tracker.

        Args:
            max_history_size: Maximum number of activity records to keep per user
        """
        self.max_history_size = max_history_size

        # Store user activity: {user_id: [{'timestamp': float, 'action': str, 'chat_id': int}, ...]}
        self._activity: dict[int, list[dict]] = {}

        # Store user statistics: {user_id: {'total_requests': int, 'first_seen': float, 'last_seen': float}}
        self._stats: dict[int, dict] = {}

        logger.info(
            f"UserActivityMiddleware initialized - Max history: {max_history_size} records per user"
        )

    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable
    ):
        """
        Track user activity and process request.

        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in the chain

        Returns:
            Handler response
        """
        if not update.effective_user:
            return await next_handler(update, context)

        user_id = update.effective_user.id
        current_time = time.time()

        # Log the activity
        self._log_activity(user_id, update, current_time)

        # Update statistics
        self._update_stats(user_id, current_time)

        # Process the request
        return await next_handler(update, context)

    def _log_activity(self, user_id: int, update: Update, timestamp: float) -> None:
        """
        Log user activity.

        Args:
            user_id: Telegram user ID
            update: Telegram update object
            timestamp: Current timestamp
        """
        if user_id not in self._activity:
            self._activity[user_id] = []

        # Determine action type
        action = self._get_action_type(update)

        # Create activity record
        activity_record = {
            "timestamp": timestamp,
            "action": action,
            "chat_id": update.effective_chat.id if update.effective_chat else None,
            "username": update.effective_user.username if update.effective_user else None,
        }

        # Add to activity history
        self._activity[user_id].append(activity_record)

        # Trim if exceeds max size
        if len(self._activity[user_id]) > self.max_history_size:
            self._activity[user_id] = self._activity[user_id][-self.max_history_size :]

        # Log activity (debug level to avoid spam)
        logger.debug(
            f"User activity - User: {user_id}, Action: {action}, "
            f"Time: {datetime.fromtimestamp(timestamp).isoformat()}"
        )

    def _update_stats(self, user_id: int, timestamp: float) -> None:
        """
        Update user statistics.

        Args:
            user_id: Telegram user ID
            timestamp: Current timestamp
        """
        if user_id not in self._stats:
            self._stats[user_id] = {
                "total_requests": 0,
                "first_seen": timestamp,
                "last_seen": timestamp,
            }

        self._stats[user_id]["total_requests"] += 1
        self._stats[user_id]["last_seen"] = timestamp

    def _get_action_type(self, update: Update) -> str:
        """
        Determine the type of user action.

        Args:
            update: Telegram update object

        Returns:
            Action type string
        """
        if update.message:
            if update.message.text:
                if update.message.text.startswith("/"):
                    return f"command/{update.message.text.split()[0]}"
                return "message/text"
            elif update.message.photo:
                return "message/photo"
            elif update.message.document:
                return "message/document"
            elif update.message.voice:
                return "message/voice"
            elif update.message.sticker:
                return "message/sticker"
            else:
                return "message/other"
        elif update.callback_query:
            return f"callback/{update.callback_query.data[:50] if update.callback_query.data else 'unknown'}"
        elif update.inline_query:
            return "inline_query"
        elif update.edited_message:
            return "edited_message"
        else:
            return "unknown"

    def get_user_activity(self, user_id: int, limit: Optional[int] = None) -> list[dict]:
        """
        Get activity history for a user.

        Args:
            user_id: Telegram user ID
            limit: Maximum number of records to return (None for all)

        Returns:
            List of activity records
        """
        if user_id not in self._activity:
            return []

        activity = self._activity[user_id]
        if limit:
            activity = activity[-limit:]

        return activity

    def get_user_stats(self, user_id: int) -> Optional[dict]:
        """
        Get statistics for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            User statistics dictionary or None if user not found
        """
        if user_id not in self._stats:
            return None

        stats = self._stats[user_id].copy()
        stats["first_seen_iso"] = datetime.fromtimestamp(stats["first_seen"]).isoformat()
        stats["last_seen_iso"] = datetime.fromtimestamp(stats["last_seen"]).isoformat()

        return stats

    def get_all_stats(self) -> dict[int, dict]:
        """
        Get statistics for all users.

        Returns:
            Dictionary of user statistics
        """
        result = {}
        for user_id, stats in self._stats.items():
            result[user_id] = self.get_user_stats(user_id)

        return result

    def get_active_users(self, since: float) -> list[int]:
        """
        Get list of users active since a specific timestamp.

        Args:
            since: Timestamp to check from

        Returns:
            List of active user IDs
        """
        active_users = []
        for user_id, stats in self._stats.items():
            if stats["last_seen"] >= since:
                active_users.append(user_id)

        return active_users

    def clear_user_activity(self, user_id: int) -> None:
        """
        Clear activity data for a user.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self._activity:
            del self._activity[user_id]
        if user_id in self._stats:
            del self._stats[user_id]
        logger.info(f"Activity data cleared for user {user_id}")

    def clear_all_activity(self) -> None:
        """Clear all activity data."""
        self._activity.clear()
        self._stats.clear()
        logger.info("All activity data cleared")
