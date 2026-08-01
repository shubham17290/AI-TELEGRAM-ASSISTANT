"""Test configuration and fixtures."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path FIRST
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file if it exists BEFORE setting any environment variables
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

# Set/override environment variables for testing
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_12345678901234567890"
os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_token_for_testing_12345678901234567890"
os.environ["OPENAI_API_KEY"] = "test_openai_key_for_testing_12345678901234567890"
os.environ["AI_PROVIDER"] = "openai"
os.environ["AI_MODEL"] = "gpt-4o-mini"
os.environ["SPAM_DETECTION_ENABLED"] = "true"
os.environ["RATE_LIMIT"] = "5"
os.environ["RATE_LIMIT_PERIOD"] = "60"
os.environ["RATE_LIMIT_WARN_ONCE"] = "true"
os.environ["LOG_REDACT_SECRETS"] = "true"
os.environ["LOG_REDACT_PII"] = "true"
os.environ["API_TIMEOUT"] = "30"
os.environ["DB_QUERY_TIMEOUT"] = "10"
os.environ["DB_POOL_TIMEOUT"] = "30"

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import connection as db_connection
from src.database.connection import close_database, get_session, init_database
from src.database.initialization import create_tables, drop_tables
from src.database.models import Chat, ConversationHistory, Settings, User


@pytest.fixture(scope="session", autouse=True)
def setup_database_engine():
    """
    Initialize the database engine once for the whole test session.

    Table creation is handled by the function-scoped ``setup_database`` fixture
    so we stay compatible with pytest-asyncio's default function loop scope.
    """
    print("Initializing database engine...")
    init_database()
    print(f"Engine after init: {db_connection.engine}")
    print(f"Session maker after init: {db_connection.async_session_maker}")

    yield

    # Best-effort sync cleanup note: async dispose is done in setup_database
    print("Database engine fixture teardown complete")


@pytest.fixture(autouse=True)
async def setup_database():
    """Ensure tables exist for each test (function-scoped async fixture)."""
    await create_tables()
    yield
    # Do not drop tables every test — clean_database truncates rows instead.



@pytest.fixture(autouse=True)
async def clean_database(db_session: AsyncSession):
    """
    Clean database before each test to ensure test isolation.

    Args:
        db_session: Database session
    """
    # Clear all tables before each test
    await db_session.execute(delete(ConversationHistory))
    await db_session.execute(delete(Settings))
    await db_session.execute(delete(Chat))
    await db_session.execute(delete(User))
    await db_session.commit()

    yield

    # Rollback any uncommitted changes after test
    await db_session.rollback()


@pytest.fixture
async def db_session() -> AsyncSession:
    """
    Create database session for testing.

    Yields:
        AsyncSession: Database session
    """
    async with get_session() as session:
        yield session
