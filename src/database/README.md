# Database Integration

This document describes the SQLite database integration using SQLAlchemy ORM with async support.

## Overview

The database layer provides:
- **SQLAlchemy ORM** with async support via `aiosqlite`
- **Repository Pattern** for clean separation of data access logic
- **Alembic migrations** for schema version control
- **SQL Injection protection** through parameterized queries

## Tech Stack

- **Database**: SQLite (via `aiosqlite` for async operations)
- **ORM**: SQLAlchemy 2.0+ with async support
- **Migrations**: Alembic
- **Connection**: Async engine with connection pooling

## Project Structure

```
src/database/
├── __init__.py              # Package exports
├── connection.py            # Database engine and session management
├── models.py                # SQLAlchemy ORM models
├── initialization.py        # Database setup utilities
├── migrations/              # Alembic migration files
│   ├── env.py              # Migration environment config
│   ├── script.py.mako      # Migration template
│   └── versions/           # Migration scripts
└── repositories/            # Repository pattern implementations
    ├── __init__.py
    ├── base.py             # Base repository with CRUD operations
    ├── user_repository.py  # User-specific operations
    ├── chat_repository.py  # Chat-specific operations
    ├── settings_repository.py  # Settings operations
    └── conversation_repository.py  # Chat history operations
```

## Database Schema

### Users Table
Stores Telegram user information.

```python
class User(Base):
    __tablename__ = "users"

    id: int (primary key)
    telegram_id: int (unique, indexed)
    username: str (optional, indexed)
    first_name: str (optional)
    last_name: str (optional)
    language_code: str (optional)
    is_bot: bool (default: False)
    is_active: bool (default: True)
    created_at: datetime (auto-generated)
    updated_at: datetime (auto-updated)
    last_activity_at: datetime (optional)
```

### Chats Table
Stores Telegram chat/group information.

```python
class Chat(Base):
    __tablename__ = "chats"

    id: int (primary key)
    telegram_chat_id: int (unique, indexed)
    chat_type: str (private, group, supergroup, channel)
    title: str (optional)
    username: str (optional)
    is_active: bool (default: True)
    created_at: datetime (auto-generated)
    updated_at: datetime (auto-updated)
```

### Settings Table
Stores user/chat-specific configurations.

```python
class Settings(Base):
    __tablename__ = "settings"

    id: int (primary key)
    user_id: int (optional, indexed) - Foreign key to users
    chat_id: int (optional, indexed) - Foreign key to chats
    key: str (indexed)
    value: str (optional)
    created_at: datetime (auto-generated)
    updated_at: datetime (auto-updated)
```

### Conversation History Table
Stores chat message logs.

```python
class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id: int (primary key)
    user_id: int (indexed) - Foreign key to users
    chat_id: int (optional, indexed) - Foreign key to chats
    role: str (user, assistant, system)
    content: str (message text)
    tokens_used: int (optional)
    model: str (optional - AI model used)
    created_at: datetime (auto-generated)
```

## Usage

### Initialization

The database is automatically initialized when the bot starts:

```python
from src.database.initialization import initialize_database

# Initialize database (creates tables if they don't exist)
await initialize_database()
```

### Using Repositories

All database operations go through repositories. Never access the database directly from handlers or business logic.

#### User Repository

```python
from src.database.repositories import UserRepository

async with get_session() as session:
    user_repo = UserRepository(session)

    # Get or create user
    user, created = await user_repo.get_or_create(
        telegram_id=123456789,
        username="johndoe",
        first_name="John",
        last_name="Doe"
    )

    # Get user by Telegram ID
    user = await user_repo.get_by_telegram_id(123456789)

    # Update last activity
    await user_repo.update_last_activity(user.id)

    # Get all active users
    active_users = await user_repo.get_active_users()
```

#### Chat Repository

```python
from src.database.repositories import ChatRepository

async with get_session() as session:
    chat_repo = ChatRepository(session)

    # Get or create chat
    chat, created = await chat_repo.get_or_create(
        telegram_chat_id=-1001234567890,
        chat_type="group",
        title="My Group"
    )

    # Get chats by type
    groups = await chat_repo.get_chats_by_type("group")
```

#### Settings Repository

```python
from src.database.repositories import SettingsRepository

async with get_session() as session:
    settings_repo = SettingsRepository(session)

    # Set global setting
    await settings_repo.set_value("language", "en")

    # Set user-specific setting
    await settings_repo.set_value("theme", "dark", user_id=123)

    # Get setting value
    theme = await settings_repo.get_value("theme", default="light", user_id=123)

    # Get all user settings
    user_settings = await settings_repo.get_user_settings(user_id=123)
```

#### Conversation Repository

```python
from src.database.repositories import ConversationRepository

async with get_session() as session:
    conv_repo = ConversationRepository(session)

    # Add message to history
    message = await conv_repo.add_message(
        user_id=123,
        role="user",
        content="Hello!",
        chat_id=456,
        tokens_used=10,
        model="gpt-4"
    )

    # Get recent messages
    recent = await conv_repo.get_recent_messages(user_id=123, limit=10)

    # Get context for AI prompting (ordered by time)
    context = await conv_repo.get_context_messages(user_id=123, limit=20)

    # Clear user history
    await conv_repo.clear_user_history(user_id=123)

    # Get total tokens used
    total_tokens = await conv_repo.get_total_tokens_used(user_id=123, days=7)
```

### Session Management

Use the session context manager for automatic transaction handling:

```python
from src.database.connection import get_session

async with get_session() as session:
    # Create repositories
    user_repo = UserRepository(session)
    chat_repo = ChatRepository(session)

    # Perform operations
    user, _ = await user_repo.get_or_create(telegram_id=123)
    chat, _ = await chat_repo.get_or_create(telegram_chat_id=456, chat_type="private")

    # Session auto-commits on success, rolls back on error
```

## Security

### SQL Injection Protection

All database operations use SQLAlchemy's ORM and parameterized queries. **Never** use raw SQL string concatenation.

✅ **Safe** - Using ORM:
```python
user = await repo.get_by_telegram_id(user_input)
```

✅ **Safe** - Using parameterized queries:
```python
result = await session.execute(
    select(User).where(User.telegram_id == user_input)
)
```

❌ **Unsafe** - Never do this:
```python
# DON'T DO THIS!
query = f"SELECT * FROM users WHERE telegram_id = {user_input}"
```

## Migrations

### Creating Migrations

When you modify models, generate a new migration:

```bash
# Auto-generate migration based on model changes
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```

### Migration Commands

```bash
# Create new migration
alembic revision --autogenerate -m "Add new column"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration version
alembic current

# Show migration history
alembic history
```

### Configuration

Alembic is configured in `alembic.ini`:
- Migration scripts location: `src/database/migrations/versions/`
- Database URL: `sqlite+aiosqlite:///telegram_bot.db` (overridden by `DATABASE_URL` env var)

## Configuration

Database settings in `.env`:

```env
# Database URL (SQLite with async driver)
DATABASE_URL=sqlite+aiosqlite:///telegram_bot.db

# Enable SQL query logging (for debugging)
DATABASE_ECHO=false
```

## Testing

The database layer includes comprehensive tests in `tests/test_database.py`:

- User repository operations
- Chat repository operations
- Settings repository operations
- Conversation history operations
- Database health checks
- SQL injection protection tests

Run tests:
```bash
pytest tests/test_database.py -v
```

## Best Practices

1. **Always use repositories** - Never access the database directly from handlers
2. **Use async sessions** - All database operations should be async
3. **Let sessions manage transactions** - Use the context manager for automatic commit/rollback
4. **Don't share sessions** - Create a new session for each operation
5. **Use parameterized queries** - SQLAlchemy ORM handles this automatically
6. **Index frequently queried fields** - Already configured in models
7. **Use migrations** - Never modify the database schema directly

## Troubleshooting

### Database Locked Error

SQLite can have locking issues with high concurrency. Solutions:
- Use WAL mode: `PRAGMA journal_mode=WAL`
- Reduce transaction duration
- Consider PostgreSQL for production

### Migration Conflicts

If you get migration conflicts:
```bash
# Check current version
alembic current

# Merge branches
alembic merge -m "Merge branches" head

# Apply merged migration
alembic upgrade head
```

### Greenlet Errors

If you see `MissingGreenlet` errors, ensure you're using async sessions and async engine:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine("sqlite+aiosqlite:///db.db")
```

## Production Considerations

For production deployments:
1. **Use PostgreSQL** instead of SQLite for better concurrency
2. **Enable connection pooling** with appropriate pool size
3. **Set up database backups** regularly
4. **Monitor query performance** with `DATABASE_ECHO=true` in development
5. **Use environment-specific databases** (dev/test/prod)
6. **Implement proper error handling** and logging
