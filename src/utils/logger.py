"""Production-grade logging configuration with multiple handlers and formatters.

Includes automatic secret redaction via SecretRedactingFilter to ensure no
sensitive information (passwords, tokens, API keys, PII) is ever written
to log files or console output.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from colorlog import ColoredFormatter
from pythonjsonlogger import jsonlogger

from src.config.settings import config
from src.utils.secret_redactor import SecretRedactingFilter


def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Setup and configure production-grade logger with multiple handlers.

    Features:
    - Colored console output for development
    - Rotating file handler for general logs
    - Separate error log file
    - Separate debug log file
    - Daily log rotation
    - Automatic log directory creation

    Args:
        name: Logger name (optional)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name or __name__)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Set the logging level
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create log directory if it doesn't exist
    log_dir = Path(config.LOG_DIR)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create log directory: {e}")
        return logger

    # Define formatters
    # JSON formatter for file handlers
    json_formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"levelname": "level", "asctime": "timestamp"},
    )

    # Text formatter for console
    text_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Colored formatter for console (development)
    colored_formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
        secondary_log_colors={},
        style="%",
    )

    # 1. Console Handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Use colored formatter in development, plain text in production
    if config.is_development:
        console_handler.setFormatter(colored_formatter)
    else:
        console_handler.setFormatter(text_formatter)

    logger.addHandler(console_handler)

    # 2. Rotating File Handler for general application logs
    # Rotates when file reaches max size (default 10MB)
    general_log_file = log_dir / f"app_{config.APP_ENV}.log"
    rotating_handler = RotatingFileHandler(
        general_log_file,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    rotating_handler.setLevel(log_level)
    rotating_handler.setFormatter(json_formatter)
    logger.addHandler(rotating_handler)

    # 3. Daily Rotating File Handler for time-based rotation
    # Creates a new log file each day
    daily_log_file = log_dir / f"app_{config.APP_ENV}_daily.log"
    daily_handler = TimedRotatingFileHandler(
        daily_log_file,
        when="midnight",
        interval=1,
        backupCount=30,  # Keep 30 days of logs
        encoding="utf-8",
    )
    daily_handler.setLevel(log_level)
    daily_handler.setFormatter(json_formatter)
    daily_handler.suffix = "%Y-%m-%d"  # Append date to rotated files
    logger.addHandler(daily_handler)

    # 4. Error File Handler - captures ERROR and CRITICAL only
    error_log_file = log_dir / f"app_{config.APP_ENV}_error.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    logger.addHandler(error_handler)

    # 5. Debug File Handler - captures DEBUG and above (only if DEBUG level is set)
    if log_level <= logging.DEBUG:
        debug_log_file = log_dir / f"app_{config.APP_ENV}_debug.log"
        debug_handler = RotatingFileHandler(
            debug_log_file,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(json_formatter)
        logger.addHandler(debug_handler)

    # 6. Secret Redaction Filter — applied to logger, root logger, and all handlers.
    # Ensures no sensitive data (tokens, keys, passwords, PII) is ever logged.
    #
    # IMPORTANT: Many modules use `logging.getLogger(__name__)` directly,
    # which creates child loggers of the ROOT logger. To guarantee redaction
    # across ALL modules (even those that bypass `src.utils.logger`), the
    # redaction filter must also be attached to the ROOT logger so that it is
    # inherited by every child logger in the application.
    if config.LOG_REDACT_SECRETS:
        redaction_filter = SecretRedactingFilter(redact_pii=config.LOG_REDACT_PII)

        # Add filter to the root logger so ALL child loggers inherit redaction
        root_logger = logging.getLogger()
        if not any(isinstance(f, SecretRedactingFilter) for f in root_logger.filters):
            root_logger.addFilter(redaction_filter)

        # Add filter to the named logger itself (applies before handler processing)
        if not any(isinstance(f, SecretRedactingFilter) for f in logger.filters):
            logger.addFilter(redaction_filter)

        # Add filter to every handler so redaction is guaranteed at output
        for handler in logger.handlers:
            if not any(isinstance(f, SecretRedactingFilter) for f in handler.filters):
                handler.addFilter(redaction_filter)

    # Log initialization message
    logger.info(
        f"Logger initialized - Environment: {config.APP_ENV}, "
        f"Level: {config.LOG_LEVEL}, Format: {config.LOG_FORMAT}, "
        f"SecretRedaction: {config.LOG_REDACT_SECRETS}"
    )

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get or create a logger instance.

    This is a convenience function that calls setup_logger.
    For subsequent calls with the same name, it returns the existing logger.

    Args:
        name: Logger name (optional)

    Returns:
        Logger instance
    """
    return setup_logger(name)
