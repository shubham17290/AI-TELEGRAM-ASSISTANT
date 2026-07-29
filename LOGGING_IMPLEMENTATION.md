# Production-Grade Logging Implementation

## Overview

This document describes the production-grade logging system implemented for the AI Telegram Assistant.

## Features Implemented

### ✅ Console Logger
- **Colored output** in development mode using `colorlog`
- **Plain text output** in production mode
- Real-time log streaming to stdout

### ✅ File Logger
- **JSON formatted** log files for structured logging
- Automatic log directory creation (`logs/`)
- Environment-specific log files (e.g., `app_development.log`, `app_production.log`)

### ✅ Rotating Logs (Size-Based)
- **RotatingFileHandler** with configurable max file size
- Default: 10MB per file (`LOG_MAX_BYTES=10485760`)
- Keeps 5 backup files (`LOG_BACKUP_COUNT=5`)
- Prevents disk space issues

### ✅ Daily Log Rotation (Time-Based)
- **TimedRotatingFileHandler** with daily rotation
- Creates new log file each day at midnight
- Keeps 30 days of historical logs
- Files named with date suffix (e.g., `app_development_daily.log.2026-07-29`)

### ✅ Error Logs
- Separate error log file: `app_{environment}_error.log`
- Captures only ERROR and CRITICAL level messages
- Includes full exception tracebacks
- Easier monitoring and alerting

### ✅ Debug Logs
- Separate debug log file: `app_{environment}_debug.log`
- Only created when `LOG_LEVEL=DEBUG`
- Captures all DEBUG and above messages
- Useful for development and troubleshooting

### ✅ Automatic Log Directory Creation
- Logs directory created automatically on first use
- Uses `Path.mkdir(parents=True, exist_ok=True)`
- No manual setup required

### ✅ Standard Logging Module
- Uses Python's built-in `logging` module
- Compatible with standard logging practices
- No custom logging framework

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Logging Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json                   # json or text
LOG_DIR=logs                      # Log directory path
LOG_MAX_BYTES=10485760           # Max file size (10MB)
LOG_BACKUP_COUNT=5               # Number of backup files
```

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages
- **ERROR**: Error messages (also logged to error file)
- **CRITICAL**: Critical errors (also logged to error file)

## Log Files Structure

```
logs/
├── app_development.log              # General application logs (rotating by size)
├── app_development_daily.log        # Daily rotated logs
├── app_development_daily.log.2026-07-29  # Archived daily log
├── app_development_error.log        # Error and critical logs only
└── app_development_debug.log        # Debug logs (only if LOG_LEVEL=DEBUG)
```

## Usage

### Basic Usage

```python
from src.utils.logger import get_logger

# Get a logger for your module
logger = get_logger(__name__)

# Use standard logging methods
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")

# Log exceptions with traceback
try:
    result = 10 / 0
except Exception:
    logger.exception("An error occurred")
```

### In Telegram Handlers

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Processing message from user {user_id}")

    try:
        # Your handler logic
        response = await process_message(update.message.text)
        logger.info(f"Successfully processed message from user {user_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)
        raise
```

### Using the Logging Middleware

```python
from src.middlewares.logging import LoggingMiddleware

# Add to your bot application
app.add_middleware(LoggingMiddleware())
```

## Log Format

### Console Output (Development)
```
2026-07-29 20:20:34,985 - test - INFO - This is an INFO message
```
With colors:
- DEBUG: Cyan
- INFO: Green
- WARNING: Yellow
- ERROR: Red
- CRITICAL: Red with white background

### File Output (JSON)
```json
{
  "name": "test",
  "message": "This is an INFO message",
  "level": "INFO",
  "timestamp": "2026-07-29 20:20:34,986"
}
```

## Production Considerations

1. **Log Level**: Set `LOG_LEVEL=INFO` or `LOG_LEVEL=WARNING` in production
2. **Log Format**: Use `LOG_FORMAT=json` for structured logging
3. **Error Monitoring**: The separate error log file is ideal for monitoring tools
4. **Log Rotation**: Prevents disk space issues in long-running applications
5. **Performance**: File handlers use buffering for optimal performance

## Testing

Run the test suite to verify the logging implementation:

```bash
python test_logging.py
```

Expected output:
- Console logs with colored output
- Multiple log files created in `logs/` directory
- All log levels working correctly
- Exception logging with tracebacks

## Dependencies

Added to `requirements.txt`:
```
colorlog==6.8.2
```

## Implementation Details

### Files Modified
- `src/utils/logger.py` - Enhanced logging configuration
- `src/config/settings.py` - Added logging configuration parameters
- `src/middlewares/logging.py` - Implemented logging middleware
- `requirements.txt` - Added colorlog dependency

### Key Components

1. **setup_logger()**: Main function to configure and return a logger
2. **get_logger()**: Convenience wrapper for setup_logger()
3. **LoggingMiddleware**: Telegram bot middleware for automatic logging

## Troubleshooting

### No logs directory created
- Check permissions in the application directory
- The logger will log a warning but continue without file logging

### Debug log file not created
- Debug logs are only created when `LOG_LEVEL=DEBUG`
- Set `LOG_LEVEL=DEBUG` in your `.env` file

### Import errors
- Ensure `colorlog` is installed: `pip install colorlog==6.8.2`
- Ensure `python-json-logger` is installed: `pip install python-json-logger==2.0.7`

## Best Practices

1. **Use module-level loggers**: `logger = get_logger(__name__)`
2. **Log appropriate levels**: Don't log everything as INFO
3. **Include context**: Add user IDs, chat IDs, etc. to log messages
4. **Use exception logging**: Use `logger.exception()` in except blocks
5. **Avoid sensitive data**: Don't log passwords, tokens, or PII
6. **Monitor error logs**: Set up alerts for ERROR and CRITICAL messages

## Future Enhancements

- Integration with external logging services (e.g., Sentry, Loggly)
- Log aggregation and analysis
- Performance metrics logging
- Request/response logging for API calls
- Audit logging for security events
