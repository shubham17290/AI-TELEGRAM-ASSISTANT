"""Database initialization and setup utilities."""

import asyncio
from pathlib import Path

from sqlalchemy import text

from src.database.connection import Base, close_database, engine, get_session, init_database
from src.database.models import Chat, ConversationHistory, Settings, User


async def create_tables() -> None:
    """Create all database tables."""
    # Import here to get the current state of the global variables
    from src.database.connection import engine as db_engine

    if db_engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all database tables."""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def reset_database() -> None:
    """Reset database by dropping and recreating all tables."""
    await drop_tables()
    await create_tables()


async def check_database_health() -> dict:
    """
    Check database health and return status.

    Returns:
        Dictionary with health check results
    """
    health = {
        "status": "healthy",
        "tables": [],
        "errors": [],
    }

    try:
        if engine is None:
            health["status"] = "unhealthy"
            health["errors"].append("Database engine not initialized")
            return health

        # Check if we can execute a simple query
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            await result.fetchone()

        # Get list of tables
        async with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            else:
                result = await conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                )
            tables = result.fetchall()
            health["tables"] = [table[0] for table in tables]

    except Exception as e:
        health["status"] = "unhealthy"
        health["errors"].append(str(e))

    return health


async def initialize_database() -> None:
    """
    Initialize database with tables and default data.

    This is the main entry point for database setup.
    """
    # Initialize database connection
    init_database()

    # Create all tables
    await create_tables()

    # Close connection (will be reopened as needed)
    await close_database()


def get_database_url() -> str:
    """
    Get the current database URL.

    Returns:
        Database URL string
    """
    from src.config.settings import get_or_create_config

    config = get_or_create_config()
    return config.DATABASE_URL


def get_database_path() -> Path:
    """
    Get the database file path (for SQLite).

    Returns:
        Path to database file
    """
    db_url = get_database_url()

    # Extract path from SQLite URL
    if "sqlite" in db_url:
        # Remove driver prefix
        if "///" in db_url:
            path = db_url.split("///")[-1]
            return Path(path)

    return Path("telegram_bot.db")
