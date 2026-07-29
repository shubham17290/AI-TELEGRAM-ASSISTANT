"""Settings repository for database operations."""

from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Settings
from src.database.repositories.base import BaseRepository


class SettingsRepository(BaseRepository[Settings]):
    """Repository for Settings model operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize settings repository.

        Args:
            session: Database session
        """
        super().__init__(Settings, session)

    async def get_by_key(
        self, key: str, user_id: Optional[int] = None, chat_id: Optional[int] = None
    ) -> Optional[Settings]:
        """
        Get setting by key.

        Args:
            key: Setting key
            user_id: User ID (optional)
            chat_id: Chat ID (optional)

        Returns:
            Setting or None if not found
        """
        query = select(Settings).where(Settings.key == key)

        if user_id is not None:
            query = query.where(Settings.user_id == user_id)
        if chat_id is not None:
            query = query.where(Settings.chat_id == chat_id)

        # If both user_id and chat_id are None, get global setting
        if user_id is None and chat_id is None:
            query = query.where(Settings.user_id.is_(None), Settings.chat_id.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_value(
        self,
        key: str,
        default: Optional[str] = None,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Get setting value by key.

        Args:
            key: Setting key
            default: Default value if not found
            user_id: User ID (optional)
            chat_id: Chat ID (optional)

        Returns:
            Setting value or default
        """
        setting = await self.get_by_key(key, user_id, chat_id)
        return setting.value if setting else default

    async def set_value(
        self,
        key: str,
        value: str,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> Settings:
        """
        Set setting value.

        Args:
            key: Setting key
            value: Setting value
            user_id: User ID (optional)
            chat_id: Chat ID (optional)

        Returns:
            Created or updated setting
        """
        setting = await self.get_by_key(key, user_id, chat_id)
        if setting:
            setting.value = value
            await self.session.flush()
            await self.session.refresh(setting)
            return setting

        return await self.create(
            key=key,
            value=value,
            user_id=user_id,
            chat_id=chat_id,
        )

    async def delete_by_key(
        self, key: str, user_id: Optional[int] = None, chat_id: Optional[int] = None
    ) -> bool:
        """
        Delete setting by key.

        Args:
            key: Setting key
            user_id: User ID (optional)
            chat_id: Chat ID (optional)

        Returns:
            True if deleted, False if not found
        """
        query = delete(Settings).where(Settings.key == key)

        if user_id is not None:
            query = query.where(Settings.user_id == user_id)
        if chat_id is not None:
            query = query.where(Settings.chat_id == chat_id)

        if user_id is None and chat_id is None:
            query = query.where(Settings.user_id.is_(None), Settings.chat_id.is_(None))

        result = await self.session.execute(query)
        return result.rowcount > 0

    async def get_user_settings(self, user_id: int) -> List[Settings]:
        """
        Get all settings for a user.

        Args:
            user_id: User ID

        Returns:
            List of user settings
        """
        result = await self.session.execute(
            select(Settings).where(Settings.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_chat_settings(self, chat_id: int) -> List[Settings]:
        """
        Get all settings for a chat.

        Args:
            chat_id: Chat ID

        Returns:
            List of chat settings
        """
        result = await self.session.execute(
            select(Settings).where(Settings.chat_id == chat_id)
        )
        return list(result.scalars().all())
