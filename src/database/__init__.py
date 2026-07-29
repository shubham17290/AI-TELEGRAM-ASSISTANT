"""Database package with SQLAlchemy and SQLite support."""

from src.database.connection import (
    Base,
    async_session_maker,
    close_database,
    engine,
    get_session,
    init_database,
)
from src.database.models import (
    Chat,
    ConversationHistory,
    Settings,
    User,
)
from src.database.repositories import (
    BaseRepository,
    ChatRepository,
    ConversationRepository,
    SettingsRepository,
    UserRepository,
)

__all__ = [
    # Connection
    "Base",
    "engine",
    "async_session_maker",
    "init_database",
    "get_session",
    "close_database",
    # Models
    "User",
    "Chat",
    "Settings",
    "ConversationHistory",
    # Repositories
    "BaseRepository",
    "UserRepository",
    "ChatRepository",
    "SettingsRepository",
    "ConversationRepository",
]
