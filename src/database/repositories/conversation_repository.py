"""Conversation history repository for database operations."""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ConversationHistory
from src.database.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[ConversationHistory]):
    """Repository for ConversationHistory model operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize conversation repository.

        Args:
            session: Database session
        """
        super().__init__(ConversationHistory, session)

    async def get_by_user_id(
        self, user_id: int, limit: Optional[int] = None, offset: int = 0
    ) -> List[ConversationHistory]:
        """
        Get conversation history for a user.

        Args:
            user_id: User ID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of conversation history records
        """
        query = (
            select(ConversationHistory)
            .where(ConversationHistory.user_id == user_id)
            .order_by(desc(ConversationHistory.created_at))
            .offset(offset)
        )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_user_id_paginated(
        self, user_id: int, page: int = 1, page_size: int = 10
    ) -> Tuple[List[ConversationHistory], int]:
        """
        Get paginated conversation history for a user.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            page_size: Number of records per page

        Returns:
            Tuple of (list of records, total count)
        """
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        if page_size > 100:
            page_size = 100  # Prevent excessive memory usage

        offset = (page - 1) * page_size

        # Get total count
        count_query = (
            select(func.count(ConversationHistory.id))
            .where(ConversationHistory.user_id == user_id)
        )
        total_result = await self.session.execute(count_query)
        total_count = total_result.scalar_one()

        # Get paginated records
        query = (
            select(ConversationHistory)
            .where(ConversationHistory.user_id == user_id)
            .order_by(desc(ConversationHistory.created_at))
            .limit(page_size)
            .offset(offset)
        )

        result = await self.session.execute(query)
        records = list(result.scalars().all())

        return records, total_count

    async def get_by_chat_id(
        self, chat_id: int, limit: Optional[int] = None, offset: int = 0
    ) -> List[ConversationHistory]:
        """
        Get conversation history for a chat.

        Args:
            chat_id: Chat ID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of conversation history records
        """
        query = (
            select(ConversationHistory)
            .where(ConversationHistory.chat_id == chat_id)
            .order_by(desc(ConversationHistory.created_at))
            .offset(offset)
        )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_chat_id_paginated(
        self, chat_id: int, page: int = 1, page_size: int = 10
    ) -> Tuple[List[ConversationHistory], int]:
        """
        Get paginated conversation history for a chat.

        Args:
            chat_id: Chat ID
            page: Page number (1-indexed)
            page_size: Number of records per page

        Returns:
            Tuple of (list of records, total count)
        """
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        if page_size > 100:
            page_size = 100  # Prevent excessive memory usage

        offset = (page - 1) * page_size

        # Get total count
        count_query = (
            select(func.count(ConversationHistory.id))
            .where(ConversationHistory.chat_id == chat_id)
        )
        total_result = await self.session.execute(count_query)
        total_count = total_result.scalar_one()

        # Get paginated records
        query = (
            select(ConversationHistory)
            .where(ConversationHistory.chat_id == chat_id)
            .order_by(desc(ConversationHistory.created_at))
            .limit(page_size)
            .offset(offset)
        )

        result = await self.session.execute(query)
        records = list(result.scalars().all())

        return records, total_count

    async def get_recent_messages(
        self, user_id: int, limit: int = 10
    ) -> List[ConversationHistory]:
        """
        Get recent messages for a user.

        Args:
            user_id: User ID
            limit: Maximum number of messages to return

        Returns:
            List of recent conversation history records
        """
        return await self.get_by_user_id(user_id, limit=limit)

    async def add_message(
        self,
        user_id: int,
        role: str,
        content: str,
        chat_id: Optional[int] = None,
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
    ) -> ConversationHistory:
        """
        Add a message to conversation history.

        Args:
            user_id: User ID
            role: Message role (user, assistant, system)
            content: Message content
            chat_id: Chat ID (optional)
            tokens_used: Number of tokens used (optional)
            model: AI model used (optional)

        Returns:
            Created conversation history record
        """
        return await self.create(
            user_id=user_id,
            chat_id=chat_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
            model=model,
        )

    async def get_context_messages(
        self, user_id: int, limit: int = 20, hours: Optional[int] = None
    ) -> List[ConversationHistory]:
        """
        Get conversation context for AI prompting.

        Args:
            user_id: User ID
            limit: Maximum number of messages to return
            hours: Only return messages from last N hours (optional)

        Returns:
            List of conversation history records ordered by creation time
        """
        query = (
            select(ConversationHistory)
            .where(ConversationHistory.user_id == user_id)
            .order_by(ConversationHistory.created_at)
        )

        if hours is not None:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            query = query.where(ConversationHistory.created_at >= cutoff_time)

        query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def clear_user_history(self, user_id: int) -> bool:
        """
        Clear all conversation history for a user.

        Args:
            user_id: User ID

        Returns:
            True if history was cleared
        """
        from sqlalchemy import delete

        query = delete(ConversationHistory).where(ConversationHistory.user_id == user_id)
        result = await self.session.execute(query)
        await self.session.flush()
        return result.rowcount > 0

    async def get_total_tokens_used(self, user_id: int, days: Optional[int] = None) -> int:
        """
        Get total tokens used by a user.

        Args:
            user_id: User ID
            days: Number of days to look back (optional)

        Returns:
            Total tokens used
        """
        query = select(ConversationHistory).where(ConversationHistory.user_id == user_id)

        if days is not None:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            query = query.where(ConversationHistory.created_at >= cutoff_time)

        result = await self.session.execute(query)
        messages = result.scalars().all()

        return sum(msg.tokens_used for msg in messages if msg.tokens_used is not None)
