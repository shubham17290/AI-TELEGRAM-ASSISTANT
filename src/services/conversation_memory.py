"""Conversation memory service for managing per-user chat history."""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


@dataclass
class Message:
    """Represents a single message in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


class ConversationMemory:
    """
    In-memory conversation history manager for each user.

    Stores the last N messages per user to maintain context while
    preventing token limit overflow.
    """

    def __init__(self, max_history: int = 10):
        """
        Initialize conversation memory.

        Args:
            max_history: Maximum number of messages to keep per user
        """
        self.max_history = max_history
        self._conversations: dict[int, deque[Message]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        self._lock = Lock()
        self._system_prompts: dict[int, str] = {}

    def add_message(self, user_id: int, role: str, content: str) -> None:
        """
        Add a message to the user's conversation history.

        Args:
            user_id: Telegram user ID
            role: Message role ("user" or "assistant")
            content: Message content
        """
        with self._lock:
            message = Message(role=role, content=content)
            self._conversations[user_id].append(message)

    def get_history(self, user_id: int) -> list[dict[str, str]]:
        """
        Get conversation history for a user in OpenAI format.

        Args:
            user_id: Telegram user ID

        Returns:
            List of messages in OpenAI chat format
        """
        with self._lock:
            messages = []

            # Add system prompt if exists
            if user_id in self._system_prompts:
                messages.append({
                    "role": "system",
                    "content": self._system_prompts[user_id]
                })

            # Add conversation history
            for msg in self._conversations[user_id]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

            return messages

    def set_system_prompt(self, user_id: int, prompt: str) -> None:
        """
        Set a custom system prompt for a user.

        Args:
            user_id: Telegram user ID
            prompt: System prompt text
        """
        with self._lock:
            self._system_prompts[user_id] = prompt

    def get_system_prompt(self, user_id: int) -> Optional[str]:
        """
        Get the system prompt for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            System prompt text or None if not set
        """
        with self._lock:
            return self._system_prompts.get(user_id)

    def clear_history(self, user_id: int) -> None:
        """
        Clear conversation history for a user.

        Args:
            user_id: Telegram user ID
        """
        with self._lock:
            if user_id in self._conversations:
                self._conversations[user_id].clear()
            if user_id in self._system_prompts:
                del self._system_prompts[user_id]

    def get_message_count(self, user_id: int) -> int:
        """
        Get the number of messages in a user's history.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of messages
        """
        with self._lock:
            return len(self._conversations[user_id])

    def clear_all(self) -> None:
        """Clear all conversation histories."""
        with self._lock:
            self._conversations.clear()
            self._system_prompts.clear()


# Global conversation memory instance
conversation_memory = ConversationMemory(max_history=10)


def get_conversation_memory() -> ConversationMemory:
    """
    Get the global conversation memory instance.

    Returns:
        ConversationMemory instance
    """
    return conversation_memory
