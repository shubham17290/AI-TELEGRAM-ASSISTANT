"""Database connection management with SQLite async support."""

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Global database engine and session factory
engine = None
async_session_maker = None


def init_database(database_url: str = None, database_echo: bool = False) -> None:
    """
    Initialize database engine and session factory.

    Args:
        database_url: Database URL (optional, uses config if not provided)
        database_echo: Enable SQL logging (optional, uses config if not provided)
    """
    global engine, async_session_maker

    # Load configuration if not provided
    if database_url is None or database_echo is None:
        try:
            from src.config.settings import get_config
            config = get_config()
            if database_url is None:
                database_url = config.DATABASE_URL
            if database_echo is None:
                database_echo = config.DATABASE_ECHO
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}") from e

    # Ensure we have the async driver prefix
    if not database_url.startswith("sqlite+aiosqlite://"):
        if database_url.startswith("sqlite://"):
            database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
        else:
            database_url = "sqlite+aiosqlite:///telegram_bot.db"

    # Load timeout config from settings
    try:
        from src.config.settings import config as app_config
        db_query_timeout = app_config.DB_QUERY_TIMEOUT
        db_pool_timeout = app_config.DB_POOL_TIMEOUT
    except Exception:
        db_query_timeout = 10
        db_pool_timeout = 30

    engine = create_async_engine(
        database_url,
        echo=database_echo,
        connect_args={"check_same_thread": False, "timeout": db_query_timeout},
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=db_pool_timeout,
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncSession:
    """Get database session for dependency injection."""
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_database() -> None:
    """Close database connections."""
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_maker = None
