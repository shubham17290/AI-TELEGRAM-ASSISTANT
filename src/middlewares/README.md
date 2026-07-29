# Middleware System

This directory contains the middleware system for the AI Telegram Assistant bot.

## Architecture

The middleware system follows a chain-of-responsibility pattern where each middleware wraps the next handler in the chain. This allows for clean separation of concerns and reusable components.

### Components

1. **Base Classes** (`base.py`)
   - `BaseMiddleware`: Abstract base class for all middlewares
   - `MiddlewareChain`: Chains multiple middlewares together

2. **Middleware Implementations**
   - `LoggingMiddleware`: Logs incoming updates and handler execution with performance tracking
   - `RateLimitMiddleware`: Rate limits requests per user to prevent abuse
   - `ExceptionHandlerMiddleware`: Catches and handles exceptions globally
   - `UserActivityMiddleware`: Tracks user interactions and maintains statistics
   - `AuthMiddleware`: Authentication placeholder (disabled by default)

3. **Registry** (`registry.py`)
   - `MiddlewareRegistry`: Central registry for managing middlewares
   - `get_registry()`: Get the global registry instance
   - `create_middleware_chain()`: Create a custom middleware chain

4. **Wrapper** (`wrapper.py`)
   - `MiddlewareHandlerWrapper`: Wraps handlers with middleware
   - `apply_middleware()`: Convenience function to apply middleware to handlers

## Usage

### Basic Usage

The middleware system is automatically initialized when the bot starts. All handlers are automatically wrapped with the default middleware chain.

### Custom Middleware Chain

```python
from src.middlewares import create_middleware_chain, get_registry

# Get specific middlewares
registry = get_registry()
logging_mw = registry.get("logging")
rate_limit_mw = registry.get("rate_limit")

# Create custom chain
custom_chain = create_middleware_chain(["logging", "rate_limit"])
```

### Creating Custom Middleware

```python
from src.middlewares.base import BaseMiddleware
from telegram import Update
from telegram.ext import ContextTypes
from typing import Callable

class CustomMiddleware(BaseMiddleware):
    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable
    ):
        # Pre-processing
        print(f"Before handler: {update.effective_user.id}")

        # Call next handler
        result = await next_handler(update, context)

        # Post-processing
        print(f"After handler: {update.effective_user.id}")

        return result

# Register custom middleware
registry = get_registry()
registry.register("custom", CustomMiddleware())
```

### Middleware Execution Order

The default middleware chain executes in this order (from innermost to outermost):

1. **ExceptionHandlerMiddleware** - Catches all exceptions
2. **AuthMiddleware** - Checks authentication (currently disabled)
3. **RateLimitMiddleware** - Enforces rate limits
4. **UserActivityMiddleware** - Tracks user activity
5. **LoggingMiddleware** - Logs everything

## Configuration

### Rate Limiting

Configure in `.env`:
```env
RATE_LIMIT=30
RATE_LIMIT_PERIOD=60
```

### User Activity

Configure when creating the middleware:
```python
from src.middlewares import UserActivityMiddleware

# Custom max history size
activity_mw = UserActivityMiddleware(max_history_size=5000)
```

### Authentication

Enable authentication (currently placeholder):
```python
from src.middlewares import AuthMiddleware

# Enable authentication
auth_mw = AuthMiddleware(enabled=True)

# Authorize users
auth_mw.authorize_user(123456789, {"role": "admin"})

# Ban users
auth_mw.ban_user(987654321, "Spam")
```

## Features

### Logging Middleware
- Logs all incoming updates with type, user, and chat info
- Tracks handler execution time
- Logs exceptions with full context

### Rate Limiter
- Per-user rate limiting
- Configurable limits and time periods
- Automatic cleanup of old requests
- User-friendly rate limit messages

### Exception Handler
- Catches all unhandled exceptions
- Logs with full traceback
- Sends user-friendly error messages
- Maps common exceptions to friendly messages

### User Activity Logger
- Tracks all user interactions
- Maintains activity history per user
- Calculates user statistics (total requests, first/last seen)
- Provides active user queries

### Authentication
- Placeholder for future authentication
- Supports user authorization and banning
- Currently disabled by default
- Ready for integration with auth systems

## API Reference

### MiddlewareRegistry

```python
registry = get_registry()

# Get middleware by name
middleware = registry.get("logging")

# Get all middlewares
all_middlewares = registry.get_all()

# Get default chain
chain = registry.get_default_chain()

# Register custom middleware
registry.register("custom", CustomMiddleware())

# Unregister middleware
registry.unregister("custom")
```

### UserActivityMiddleware

```python
activity_mw = UserActivityMiddleware()

# Get user activity history
activity = activity_mw.get_user_activity(user_id=123, limit=10)

# Get user statistics
stats = activity_mw.get_user_stats(user_id=123)
# Returns: {
#     'total_requests': 42,
#     'first_seen': 1234567890.0,
#     'last_seen': 1234567899.0,
#     'first_seen_iso': '2024-01-01T00:00:00',
#     'last_seen_iso': '2024-01-01T00:01:39'
# }

# Get all user stats
all_stats = activity_mw.get_all_stats()

# Get active users since timestamp
active_users = activity_mw.get_active_users(since=time.time() - 3600)
```

### RateLimitMiddleware

```python
rate_limit_mw = RateLimitMiddleware(rate_limit=30, period=60)

# Get remaining requests for user
remaining = rate_limit_mw.get_user_remaining_requests(user_id=123)

# Reset user limits
rate_limit_mw.reset_user_limits(user_id=123)

# Clear all limits
rate_limit_mw.clear_all_limits()
```

### AuthMiddleware

```python
auth_mw = AuthMiddleware(enabled=True)

# Authorize user
auth_mw.authorize_user(user_id=123, user_data={"role": "admin"})

# Ban user
auth_mw.ban_user(user_id=456, reason="Spam")

# Unban user
auth_mw.unban_user(user_id=456)

# Check authorization
is_auth = auth_mw.is_authorized(user_id=123)
is_banned = auth_mw.is_banned(user_id=456)

# Get lists
authorized = auth_mw.get_authorized_users()
banned = auth_mw.get_banned_users()
```

## Testing

Run middleware tests:
```bash
pytest tests/test_middlewares.py -v
```

Run with coverage:
```bash
pytest tests/test_middlewares.py --cov=src/middlewares --cov-report=html
```

## Clean Architecture

The middleware system follows clean architecture principles:

- **Independence**: Middlewares are independent and reusable
- **Single Responsibility**: Each middleware has one clear purpose
- **Dependency Injection**: Middlewares receive dependencies through constructors
- **Interface Segregation**: Base middleware interface is minimal
- **Open/Closed**: Easy to add new middlewares without modifying existing ones

## Best Practices

1. **Order Matters**: Place exception handlers innermost, logging outermost
2. **Async All The Way**: All middlewares are async for consistency
3. **Fail Safe**: Middlewares should not crash the bot
4. **Logging**: Use appropriate log levels (debug for frequent events)
5. **Configuration**: Use environment variables for configurable values
6. **Testing**: Each middleware should have comprehensive tests
