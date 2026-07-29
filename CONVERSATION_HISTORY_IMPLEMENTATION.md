# Phase 8 — Conversation History Implementation

## Overview
This document describes the complete conversation logging system implemented for the Telegram Chatbot using SQLAlchemy ORM.

## Implementation Summary

### 1. Database Model Enhancement (`src/database/models.py`)

**Updated `ConversationHistory` model with:**
- New column: `conversation_context` (String, nullable, indexed) - for storing session_id or metadata
- Explicit composite indexes for optimal query performance:
  - `idx_conversation_user_chat_created` - (user_id, chat_id, created_at)
  - `idx_conversation_user_created` - (user_id, created_at)
  - `idx_conversation_chat_created` - (chat_id, created_at)

**Required columns:**
- `id` - Primary Key
- `user_id` - Telegram user ID (indexed)
- `chat_id` - Telegram chat ID (indexed)
- `role` - Message role (user/assistant/system)
- `content` - Message content
- `timestamp` - UTC timestamp (created_at)
- `conversation_context` - Session ID or metadata (indexed)
- `tokens_used` - Optional token count
- `model` - AI model used

### 2. Repository Layer Enhancement (`src/database/repositories/conversation_repository.py`)

**Added pagination methods:**
- `get_by_user_id_paginated(user_id, page, page_size)` - Returns tuple of (records, total_count)
- `get_by_chat_id_paginated(chat_id, page, page_size)` - Returns tuple of (records, total_count)

**Features:**
- Strict pagination with limit/offset
- Parameter validation (page >= 1, page_size capped at 100)
- Total count query for pagination UI
- Never loads entire history into memory

### 3. Conversation Logger Service (`src/services/conversation_logger.py`)

**New service providing:**
- `log_user_message()` - Logs incoming user messages
- `log_assistant_message()` - Logs AI responses with token usage
- `get_user_history_paginated()` - Retrieves paginated user history
- `get_chat_history_paginated()` - Retrieves paginated chat history

**Error handling:**
- Graceful failure - logging errors don't break the bot
- Proper session management using async context managers

### 4. Bot Integration (`src/handlers/message_handler.py`)

**Modified `handle_message()` to:**
- Log every incoming user message to database
- Log every outgoing AI response to database
- Use proper session management with `async with get_session()`
- Capture chat_id from `update.effective_chat.id`

**Flow:**
1. User sends message
2. Message logged to database (user role)
3. AI generates response with streaming
4. Final response logged to database (assistant role)

### 5. History Command (`src/handlers/command_handlers.py`)

**New `/history` command:**
- Usage: `/history <page_number>`
- Shows 5 messages per page
- Displays formatted conversation history with:
  - Role indicators (👤 User / 🤖 AI)
  - Timestamps
  - Truncated messages (100 chars max)
  - Pagination info and navigation

**Features:**
- Input validation (page number parsing)
- Empty state handling
- Total message count display
- Navigation hints

### 6. Handler Registration (`src/handlers/__init__.py`)

**Added:**
- Import of `history_command`
- Registration of `/history` command handler with middleware

## Database Indexes

The implementation includes three composite indexes for optimal performance:

```python
__table_args__ = (
    Index('idx_conversation_user_chat_created', 'user_id', 'chat_id', 'created_at'),
    Index('idx_conversation_user_created', 'user_id', 'created_at'),
    Index('idx_conversation_chat_created', 'chat_id', 'created_at'),
)
```

These indexes ensure fast lookups for:
- User-specific history queries
- Chat-specific history queries
- Combined user+chat queries
- Time-based filtering

## Testing

**Added comprehensive tests in `tests/test_database.py`:**

1. `test_paginated_history_user` - Tests user-based pagination with 15 messages
2. `test_paginated_history_chat` - Tests chat-based pagination with 12 messages
3. `test_pagination_edge_cases` - Tests invalid pages, page size limits, empty history

**All tests pass:**
```
tests/test_database.py::TestConversationRepository::test_paginated_history_user PASSED
tests/test_database.py::TestConversationRepository::test_paginated_history_chat PASSED
tests/test_database.py::TestConversationRepository::test_pagination_edge_cases PASSED
```

## Usage Examples

### For Users
```
/history          # Shows page 1 of conversation history
/history 2        # Shows page 2
/history 3        # Shows page 3
```

### For Developers

**Logging a message:**
```python
async with get_session() as session:
    logger = ConversationLogger(session)
    await logger.log_user_message(
        user_id=123,
        content="Hello!",
        chat_id=456
    )
```

**Retrieving paginated history:**
```python
async with get_session() as session:
    logger = ConversationLogger(session)
    records, total_count = await logger.get_user_history_paginated(
        user_id=123,
        page=1,
        page_size=10
    )
```

## Performance Considerations

1. **Pagination**: Never loads full history into memory
2. **Indexes**: Composite indexes on frequently queried columns
3. **Session Management**: Proper async context managers prevent connection leaks
4. **Error Handling**: Logging failures are non-blocking
5. **Parameter Validation**: Prevents excessive memory usage (page_size max 100)

## Code Quality

- ✅ Clean, modular code structure
- ✅ Proper async/await patterns
- ✅ Type hints throughout
- ✅ Comprehensive docstrings
- ✅ Error handling with logging
- ✅ Safe database transactions
- ✅ No SQL injection vulnerabilities (using SQLAlchemy ORM)

## Migration Notes

The `conversation_context` column is nullable, so existing databases will need to:

1. Add the new column (nullable initially)
2. Create the composite indexes
3. Optionally backfill conversation_context data

For SQLite, the table will be recreated automatically on next run. For PostgreSQL, use:
```sql
ALTER TABLE conversation_history ADD COLUMN conversation_context VARCHAR;
CREATE INDEX idx_conversation_user_chat_created ON conversation_history(user_id, chat_id, created_at);
CREATE INDEX idx_conversation_user_created ON conversation_history(user_id, created_at);
CREATE INDEX idx_conversation_chat_created ON conversation_history(chat_id, created_at);
```

## Next Steps

Potential enhancements:
1. Cursor-based pagination for better performance with large datasets
2. Conversation context/session management table
3. Message search functionality
4. Export conversation history
5. Conversation analytics and statistics
