"""Database models for the Telegram bot."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from src.database.connection import Base


class User(Base):
    """User model for Telegram users."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String, nullable=True)
    is_bot = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_activity_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


class Chat(Base):
    """Chat model for Telegram chats/groups."""
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    telegram_chat_id = Column(Integer, unique=True, index=True, nullable=False)
    chat_type = Column(String, nullable=False)  # private, group, supergroup, channel
    title = Column(String, nullable=True)
    username = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Chat(telegram_chat_id={self.telegram_chat_id}, type={self.chat_type})>"


class Settings(Base):
    """Settings model for user/chat-specific settings."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    chat_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Settings(key={self.key}, value={self.value})>"


class ConversationHistory(Base):
    """Conversation history model for storing chat messages."""
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    chat_id = Column(Integer, nullable=True, index=True)
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=True)
    model = Column(String, nullable=True)
    conversation_context = Column(String, nullable=True, index=True)  # session_id or metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Explicit composite indexes for optimal query performance
    __table_args__ = (
        Index('idx_conversation_user_chat_created', 'user_id', 'chat_id', 'created_at'),
        Index('idx_conversation_user_created', 'user_id', 'created_at'),
        Index('idx_conversation_chat_created', 'chat_id', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<ConversationHistory(user_id={self.user_id}, role={self.role})>"
