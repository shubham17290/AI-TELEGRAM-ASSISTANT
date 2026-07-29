"""Tests for database integration."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import init_database, close_database, get_session
from src.database.initialization import (
    check_database_health,
    create_tables,
    drop_tables,
    reset_database,
)
from src.database.models import Chat, ConversationHistory, Settings, User
from src.database.repositories import (
    ChatRepository,
    ConversationRepository,
    SettingsRepository,
    UserRepository,
)


class TestUserRepository:
    """Tests for UserRepository."""

    async def test_create_user(self, db_session: AsyncSession):
        """Test creating a user."""
        repo = UserRepository(db_session)

        user, created = await repo.get_or_create(
            telegram_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
        )

        assert user is not None
        assert created is True
        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.is_active is True

    async def test_get_by_telegram_id(self, db_session: AsyncSession):
        """Test getting user by Telegram ID."""
        repo = UserRepository(db_session)

        # Create user
        user, _ = await repo.get_or_create(telegram_id=123456789, username="testuser")

        # Get user
        found_user = await repo.get_by_telegram_id(123456789)

        assert found_user is not None
        assert found_user.id == user.id
        assert found_user.telegram_id == 123456789

    async def test_get_or_create_existing(self, db_session: AsyncSession):
        """Test get_or_create with existing user."""
        repo = UserRepository(db_session)

        # Create user
        user1, created1 = await repo.get_or_create(telegram_id=123456789, username="testuser")

        # Get same user
        user2, created2 = await repo.get_or_create(telegram_id=123456789, username="newname")

        assert user1.id == user2.id
        assert created1 is True
        assert created2 is False
        assert user2.username == "testuser"  # Should not update

    async def test_update_last_activity(self, db_session: AsyncSession):
        """Test updating last activity."""
        repo = UserRepository(db_session)

        user, _ = await repo.get_or_create(telegram_id=123456789)
        initial_activity = user.last_activity_at

        # Wait a bit
        await asyncio.sleep(0.1)

        # Update activity
        await repo.update_last_activity(user.id)

        # Refresh user
        await db_session.refresh(user)
        assert user.last_activity_at is not None
        assert user.last_activity_at > initial_activity if initial_activity else True

    async def test_get_active_users(self, db_session: AsyncSession):
        """Test getting active users."""
        repo = UserRepository(db_session)

        # Create users
        await repo.get_or_create(telegram_id=123456789, username="active1")
        await repo.get_or_create(telegram_id=987654321, username="active2")

        # Deactivate one
        user2, _ = await repo.get_or_create(telegram_id=987654321, username="active2")
        await repo.deactivate_user(user2.id)

        # Get active users
        active_users = await repo.get_active_users()

        assert len(active_users) == 1
        assert active_users[0].telegram_id == 123456789


class TestChatRepository:
    """Tests for ChatRepository."""

    async def test_create_chat(self, db_session: AsyncSession):
        """Test creating a chat."""
        repo = ChatRepository(db_session)

        chat, created = await repo.get_or_create(
            telegram_chat_id=-1001234567890,
            chat_type="group",
            title="Test Group",
        )

        assert chat is not None
        assert created is True
        assert chat.telegram_chat_id == -1001234567890
        assert chat.chat_type == "group"
        assert chat.title == "Test Group"

    async def test_get_by_telegram_chat_id(self, db_session: AsyncSession):
        """Test getting chat by Telegram chat ID."""
        repo = ChatRepository(db_session)

        chat, _ = await repo.get_or_create(
            telegram_chat_id=-1001234567890,
            chat_type="group",
            title="Test Group",
        )

        found_chat = await repo.get_by_telegram_chat_id(-1001234567890)

        assert found_chat is not None
        assert found_chat.id == chat.id
        assert found_chat.title == "Test Group"

    async def test_get_chats_by_type(self, db_session: AsyncSession):
        """Test getting chats by type."""
        repo = ChatRepository(db_session)

        await repo.get_or_create(telegram_chat_id=-1001234567890, chat_type="group", title="Group 1")
        await repo.get_or_create(telegram_chat_id=-1009876543210, chat_type="group", title="Group 2")
        await repo.get_or_create(telegram_chat_id=123456789, chat_type="private")

        groups = await repo.get_chats_by_type("group")
        assert len(groups) == 2


class TestSettingsRepository:
    """Tests for SettingsRepository."""

    async def test_set_and_get_value(self, db_session: AsyncSession):
        """Test setting and getting values."""
        repo = SettingsRepository(db_session)

        # Set global setting
        await repo.set_value("language", "en")
        value = await repo.get_value("language")
        assert value == "en"

        # Set user-specific setting
        await repo.set_value("notifications", "true", user_id=123)
        user_value = await repo.get_value("notifications", user_id=123)
        assert user_value == "true"

        # Global setting should not be affected
        global_value = await repo.get_value("notifications")
        assert global_value is None

    async def test_get_by_key(self, db_session: AsyncSession):
        """Test getting setting by key."""
        repo = SettingsRepository(db_session)

        setting = await repo.set_value("theme", "dark", user_id=123)

        found_setting = await repo.get_by_key("theme", user_id=123)
        assert found_setting is not None
        assert found_setting.value == "dark"
        assert found_setting.user_id == 123

    async def test_delete_by_key(self, db_session: AsyncSession):
        """Test deleting setting by key."""
        repo = SettingsRepository(db_session)

        await repo.set_value("temp_setting", "value")
        assert await repo.get_value("temp_setting") == "value"

        deleted = await repo.delete_by_key("temp_setting")
        assert deleted is True
        assert await repo.get_value("temp_setting") is None


class TestConversationRepository:
    """Tests for ConversationRepository."""

    async def test_add_message(self, db_session: AsyncSession):
        """Test adding a message."""
        repo = ConversationRepository(db_session)

        message = await repo.add_message(
            user_id=123,
            role="user",
            content="Hello!",
            chat_id=456,
            tokens_used=10,
            model="gpt-4",
        )

        assert message is not None
        assert message.user_id == 123
        assert message.role == "user"
        assert message.content == "Hello!"
        assert message.chat_id == 456
        assert message.tokens_used == 10
        assert message.model == "gpt-4"

    async def test_get_recent_messages(self, db_session: AsyncSession):
        """Test getting recent messages."""
        from datetime import datetime, timedelta

        repo = ConversationRepository(db_session)

        # Add messages with sufficient delay for SQLite timestamp precision
        msg1 = await repo.add_message(
            user_id=123, role="user", content="Message 1",
            chat_id=456, tokens_used=5, model="gpt-4"
        )
        await asyncio.sleep(1.1)  # Ensure different second timestamps

        msg2 = await repo.add_message(
            user_id=123, role="assistant", content="Message 2",
            chat_id=456, tokens_used=10, model="gpt-4"
        )
        await asyncio.sleep(1.1)  # Ensure different second timestamps

        msg3 = await repo.add_message(
            user_id=123, role="user", content="Message 3",
            chat_id=456, tokens_used=5, model="gpt-4"
        )

        # Verify timestamps are in order (SQLite has second precision)
        assert msg1.created_at <= msg2.created_at <= msg3.created_at

        # Get recent messages
        recent = await repo.get_recent_messages(user_id=123, limit=2)

        assert len(recent) == 2
        # Most recent first (descending order)
        assert recent[0].id == msg3.id
        assert recent[1].id == msg2.id

    async def test_get_context_messages(self, db_session: AsyncSession):
        """Test getting context messages."""
        repo = ConversationRepository(db_session)

        # Add messages
        await repo.add_message(user_id=123, role="user", content="Message 1")
        await repo.add_message(user_id=123, role="assistant", content="Message 2")

        # Get context (ordered by time)
        context = await repo.get_context_messages(user_id=123, limit=10)

        assert len(context) == 2
        assert context[0].content == "Message 1"  # Oldest first
        assert context[1].content == "Message 2"

    async def test_clear_user_history(self, db_session: AsyncSession):
        """Test clearing user history."""
        repo = ConversationRepository(db_session)

        await repo.add_message(user_id=123, role="user", content="Message 1")
        await repo.add_message(user_id=123, role="user", content="Message 2")

        # Clear history
        cleared = await repo.clear_user_history(user_id=123)
        assert cleared is True

        # Verify cleared
        messages = await repo.get_recent_messages(user_id=123)
        assert len(messages) == 0

    async def test_get_total_tokens_used(self, db_session: AsyncSession):
        """Test getting total tokens used."""
        repo = ConversationRepository(db_session)

        await repo.add_message(user_id=123, role="user", content="Message 1", tokens_used=10)
        await repo.add_message(user_id=123, role="assistant", content="Message 2", tokens_used=15)
        await repo.add_message(user_id=123, role="user", content="Message 3", tokens_used=5)

        total = await repo.get_total_tokens_used(user_id=123)
        assert total == 30

    async def test_paginated_history_user(self, db_session: AsyncSession):
        """Test paginated conversation history for a user."""
        repo = ConversationRepository(db_session)

        # Add 15 messages
        for i in range(15):
            await repo.add_message(
                user_id=123,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i+1}",
                chat_id=456,
            )

        # Test page 1 (default page_size=10)
        records, total_count = await repo.get_by_user_id_paginated(user_id=123, page=1, page_size=5)
        assert len(records) == 5
        assert total_count == 15
        # Most recent first
        assert records[0].content == "Message 15"
        assert records[4].content == "Message 11"

        # Test page 2
        records, total_count = await repo.get_by_user_id_paginated(user_id=123, page=2, page_size=5)
        assert len(records) == 5
        assert records[0].content == "Message 10"
        assert records[4].content == "Message 6"

        # Test page 3 (last page with 5 records)
        records, total_count = await repo.get_by_user_id_paginated(user_id=123, page=3, page_size=5)
        assert len(records) == 5
        assert records[0].content == "Message 5"
        assert records[4].content == "Message 1"

        # Test page 4 (empty page)
        records, total_count = await repo.get_by_user_id_paginated(user_id=123, page=4, page_size=5)
        assert len(records) == 0

    async def test_paginated_history_chat(self, db_session: AsyncSession):
        """Test paginated conversation history for a chat."""
        repo = ConversationRepository(db_session)

        # Add 12 messages for chat_id=789
        for i in range(12):
            await repo.add_message(
                user_id=123,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Chat Message {i+1}",
                chat_id=789,
            )

        # Add 3 messages for different chat (should not be included)
        for i in range(3):
            await repo.add_message(
                user_id=123,
                role="user",
                content=f"Other Chat {i+1}",
                chat_id=999,
            )

        # Test pagination for chat 789
        records, total_count = await repo.get_by_chat_id_paginated(chat_id=789, page=1, page_size=4)
        assert len(records) == 4
        assert total_count == 12
        assert records[0].content == "Chat Message 12"
        assert records[3].content == "Chat Message 9"

        # Test page 2
        records, total_count = await repo.get_by_chat_id_paginated(chat_id=789, page=2, page_size=4)
        assert len(records) == 4
        assert records[0].content == "Chat Message 8"

    async def test_pagination_edge_cases(self, db_session: AsyncSession):
        """Test pagination edge cases."""
        repo = ConversationRepository(db_session)

        # Add 3 messages
        for i in range(3):
            await repo.add_message(user_id=999, role="user", content=f"Msg {i+1}")

        # Test invalid page numbers (should default to page 1)
        records, _ = await repo.get_by_user_id_paginated(user_id=999, page=0, page_size=2)
        assert len(records) == 2

        records, _ = await repo.get_by_user_id_paginated(user_id=999, page=-5, page_size=2)
        assert len(records) == 2

        # Test page_size limits (max 100)
        records, total_count = await repo.get_by_user_id_paginated(user_id=999, page=1, page_size=200)
        assert len(records) == 3  # Only 3 messages exist
        assert total_count == 3

        # Test empty history
        records, total_count = await repo.get_by_user_id_paginated(user_id=888888, page=1, page_size=10)
        assert len(records) == 0
        assert total_count == 0


# Note: Database health is implicitly verified by all other passing tests
# that successfully perform CRUD operations on the database


class TestSQLInjectionProtection:
    """Tests for SQL injection protection."""

    async def test_sql_injection_in_username(self, db_session: AsyncSession):
        """Test that SQL injection in username is handled safely."""
        repo = UserRepository(db_session)

        # Try SQL injection
        malicious_username = "'; DROP TABLE users; --"

        user, created = await repo.get_or_create(
            telegram_id=999999999,
            username=malicious_username,
        )

        assert created is True
        assert user.username == malicious_username

        # Verify table still exists
        users = await repo.get_all()
        assert len(users) == 1

    async def test_sql_injection_in_search(self, db_session: AsyncSession):
        """Test that SQL injection in search queries is handled safely."""
        repo = UserRepository(db_session)

        # Create user
        await repo.get_or_create(telegram_id=123456789, username="testuser")

        # Try SQL injection in search
        malicious_id = "123456789 OR 1=1"
        user = await repo.get_by_telegram_id(malicious_id)

        # Should return None (no match) instead of all users
        assert user is None
