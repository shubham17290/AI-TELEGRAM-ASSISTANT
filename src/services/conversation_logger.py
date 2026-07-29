"""Conversation logging service for database operations."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class ConversationLogger:
    """
    Service for logging conversation messages to the database.

    Provides a clean interface for logging user messages and AI responses
    with proper session management and error handling.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize conversation logger.

        Args:
            session: Database session
        """
        self.session = session
        self.repository = ConversationRepository(session)

    async def log_user_message(
        self,
        user_id: int,
        content: str,
        chat_id: Optional[int] = None,
        conversation_context: Optional[str] = None,
    ) -> None:
        """
        Log a user message to the database.

        Args:
            user_id: Telegram user ID
            content: Message content
            chat_id: Chat ID (optional)
            conversation_context: Session ID or metadata (optional)
        """
        try:
            await self.repository.add_message(
                user_id=user_id,
                role="user",
                content=content,
                chat_id=chat_id,
            )

            # Update conversation_context if provided
            if conversation_context:
                # Note: In a production system, you might want to store this
                # in a separate session management table
                pass

            logger.debug(f"Logged user message for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to log user message: {e}", exc_info=True)
            # Don't raise - logging failures shouldn't break the bot

    async def log_assistant_message(
        self,
        user_id: int,
        content: str,
        chat_id: Optional[int] = None,
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
        conversation_context: Optional[str] = None,
    ) -> None:
        """
        Log an assistant (AI) response to the database.

        Args:
            user_id: Telegram user ID
            content: Response content
            chat_id: Chat ID (optional)
            tokens_used: Number of tokens used (optional)
            model: AI model used (optional)
            conversation_context: Session ID or metadata (optional)
        """
        try:
            await self.repository.add_message(
                user_id=user_id,
                role="assistant",
                content=content,
                chat_id=chat_id,
                tokens_used=tokens_used,
                model=model,
            )
            logger.debug(f"Logged assistant message for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to log assistant message: {e}", exc_info=True)
            # Don't raise - logging failures shouldn't break the bot

    async def get_user_history_paginated(
        self, user_id: int, page: int = 1, page_size: int = 10
    ):
        """
        Get paginated conversation history for a user.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            page_size: Number of records per page

        Returns:
            Tuple of (list of records, total count)
        """
        return await self.repository.get_by_user_id_paginated(
            user_id=user_id, page=page, page_size=page_size
        )

    async def get_chat_history_paginated(
        self, chat_id: int, page: int = 1, page_size: int = 10
    ):
        """
        Get paginated conversation history for a chat.

        Args:
            chat_id: Chat ID
            page: Page number (1-indexed)
            page_size: Number of records per page

        Returns:
            Tuple of (list of records, total count)
        """
        return await self.repository.get_by_chat_id_paginated(
            chat_id=chat_id, page=page, page_size=page_size
        )
