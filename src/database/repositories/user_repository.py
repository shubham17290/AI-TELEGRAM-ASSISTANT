"""User repository for database operations."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import Base
from src.database.models import User
from src.database.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize user repository.

        Args:
            session: Database session
        """
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User or None if not found
        """
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
        is_bot: bool = False,
    ) -> tuple[User, bool]:
        """
        Get existing user or create new one.

        Args:
            telegram_id: Telegram user ID
            username: Username
            first_name: First name
            last_name: Last name
            language_code: Language code
            is_bot: Is bot user

        Returns:
            Tuple of (user, created) where created is True if new user
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False

        user = await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            is_bot=is_bot,
        )
        return user, True

    async def update_last_activity(self, user_id: int) -> None:
        """
        Update user's last activity timestamp.

        Args:
            user_id: User ID
        """
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_activity_at=datetime.utcnow())
        )
        await self.session.flush()

    async def get_active_users(self) -> List[User]:
        """
        Get all active users.

        Returns:
            List of active users
        """
        result = await self.session.execute(
            select(User).where(User.is_active == True)
        )
        return list(result.scalars().all())

    async def deactivate_user(self, user_id: int) -> bool:
        """
        Deactivate user.

        Args:
            user_id: User ID

        Returns:
            True if deactivated, False if not found
        """
        return await self.update(user_id, is_active=False) is not None
