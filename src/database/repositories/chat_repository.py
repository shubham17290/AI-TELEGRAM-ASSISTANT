"""Chat repository for database operations."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Chat
from src.database.repositories.base import BaseRepository


class ChatRepository(BaseRepository[Chat]):
    """Repository for Chat model operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize chat repository.

        Args:
            session: Database session
        """
        super().__init__(Chat, session)

    async def get_by_telegram_chat_id(self, telegram_chat_id: int) -> Optional[Chat]:
        """
        Get chat by Telegram chat ID.

        Args:
            telegram_chat_id: Telegram chat ID

        Returns:
            Chat or None if not found
        """
        result = await self.session.execute(
            select(Chat).where(Chat.telegram_chat_id == telegram_chat_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_chat_id: int,
        chat_type: str,
        title: Optional[str] = None,
        username: Optional[str] = None,
    ) -> tuple[Chat, bool]:
        """
        Get existing chat or create new one.

        Args:
            telegram_chat_id: Telegram chat ID
            chat_type: Chat type (private, group, supergroup, channel)
            title: Chat title
            username: Chat username

        Returns:
            Tuple of (chat, created) where created is True if new chat
        """
        chat = await self.get_by_telegram_chat_id(telegram_chat_id)
        if chat:
            return chat, False

        chat = await self.create(
            telegram_chat_id=telegram_chat_id,
            chat_type=chat_type,
            title=title,
            username=username,
        )
        return chat, True

    async def get_active_chats(self) -> List[Chat]:
        """
        Get all active chats.

        Returns:
            List of active chats
        """
        result = await self.session.execute(
            select(Chat).where(Chat.is_active == True)
        )
        return list(result.scalars().all())

    async def get_chats_by_type(self, chat_type: str) -> List[Chat]:
        """
        Get chats by type.

        Args:
            chat_type: Chat type (private, group, supergroup, channel)

        Returns:
            List of chats of specified type
        """
        result = await self.session.execute(
            select(Chat).where(Chat.chat_type == chat_type)
        )
        return list(result.scalars().all())
