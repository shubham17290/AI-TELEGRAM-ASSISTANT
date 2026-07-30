"""Secret redaction filter for the logging system.

This module provides a logging filter that automatically redacts sensitive
information (API keys, tokens, passwords, PII) from log messages before they
are written to any handler. It uses regex patterns to identify and mask
sensitive data.

Usage:
    from src.utils.secret_redactor import SecretRedactingFilter

    # Add to any handler
    handler.addFilter(SecretRedactingFilter())

    # Or use the helper to configure all handlers on a logger
    from src.utils.secret_redactor import add_redaction_filter_to_logger
    add_redaction_filter_to_logger(logger)
"""

import logging
import re
from typing import Optional

from src.config.settings import config


# ---------------------------------------------------------------------------
# Regex patterns for sensitive data detection
# ---------------------------------------------------------------------------

# Key-value patterns: matches `key=value`, `key: value`, `key=value` in quotes
# Captures the key name and the separator, then masks the value.
_KEY_VALUE_PATTERNS = [
    # password=secret, password: secret, "password": "secret"
    re.compile(
        r'(?i)((?:password|passwd|pwd|secret|api[_-]?key|api[_-]?secret|'
        r'access[_-]?token|auth[_-]?token|bot[_-]?token|private[_-]?key|'
        r'client[_-]?secret|refresh[_-]?token|bearer)\s*[:=]\s*)'
        r'(?:"([^"]*)"|\'([^\']*)\'|(\S+))',
    ),
    # Authorization: Bearer <token>
    re.compile(
        r'(?i)((?:authorization|proxy-authorization)\s*[:=]\s*'
        r'(?:bearer|basic|digest|token)\s+)(\S+)',
    ),
]

# Standalone token patterns (long hex/base64 strings that look like secrets)
_TOKEN_PATTERNS = [
    # Telegram bot tokens: 123456789:ABCdef...
    re.compile(r'\b(\d{8,12}:[A-Za-z0-9_-]{30,})\b'),
    # OpenAI API keys: sk-...
    re.compile(r'\b(sk-[A-Za-z0-9]{20,})\b'),
    # Anthropic API keys: sk-ant-...
    re.compile(r'\b(sk-ant-[A-Za-z0-9_-]{20,})\b'),
    # Generic long hex strings (40+ chars, likely SHA1/hash/token)
    re.compile(r'\b([a-f0-9]{40,})\b', re.IGNORECASE),
    # JWT tokens (header.payload.signature)
    re.compile(r'\b(eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b'),
]

# PII patterns
_PII_PATTERNS = [
    # Email addresses
    re.compile(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'),
    # Phone numbers (international format)
    re.compile(r'\b(\+\d{1,3}[\s.-]?\d{1,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4})\b'),
]

# Credit card number pattern (basic Luhn-like format check)
_CREDIT_CARD_PATTERN = re.compile(
    r'\b((?:\d[ -]*?){13,16})\b'
)

# Database URL with credentials: postgres://user:pass@host/db
_DB_URL_PATTERN = re.compile(
    r'((?:postgres|mysql|redis|mongodb|amqp)://[^:\s]+:)([^@\s]+)(@)',
)

# Redaction placeholder
_REDACTED = "[REDACTED]"


class SecretRedactingFilter(logging.Filter):
    """Logging filter that redacts sensitive information from log records.

    This filter scans log messages (and optionally exception tracebacks) for
    known sensitive patterns and replaces them with ``[REDACTED]`` before
    the record is passed to handlers.

    Patterns detected:
        - Key-value pairs (password=..., api_key: ..., etc.)
        - Telegram bot tokens
        - OpenAI / Anthropic API keys
        - JWT tokens
        - Generic long hex strings (hashes/tokens)
        - Email addresses
        - Phone numbers
        - Credit card numbers
        - Database URLs with embedded credentials
    """

    def __init__(self, redact_pii: bool = True, redact_traceback: bool = True):
        """Initialize the redaction filter.

        Args:
            redact_pii: If True, also redact PII (emails, phone numbers).
            redact_traceback: If True, also redact exc_info traceback strings.
        """
        super().__init__()
        self.redact_pii = redact_pii
        self.redact_traceback = redact_traceback

        # Collect active secret patterns
        self._secret_patterns = list(_KEY_VALUE_PATTERNS) + list(_TOKEN_PATTERNS)
        self._secret_patterns.append(_DB_URL_PATTERN)

        if self.redact_pii:
            self._secret_patterns.extend(_PII_PATTERNS)
            self._secret_patterns.append(_CREDIT_CARD_PATTERN)

        # Also collect known secrets from config for exact-match redaction
        self._known_secrets: list[str] = []
        self._load_known_secrets()

    def _load_known_secrets(self) -> None:
        """Load known secret values from configuration for exact matching."""
        secret_attrs = [
            "TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "SECRET_KEY",
        ]

        for attr in secret_attrs:
            try:
                value = getattr(config, attr, None)
                if value and isinstance(value, str) and len(value) >= 8:
                    self._known_secrets.append(value)
            except Exception:
                # Config might not be loaded yet; skip silently
                pass

    def _redact_text(self, text: str) -> str:
        """Apply all redaction patterns to a text string.

        Args:
            text: The original text to redact.

        Returns:
            The text with sensitive values replaced by ``[REDACTED]``.
        """
        if not text:
            return text

        # First, redact known secrets (exact match) — most reliable
        for secret in self._known_secrets:
            if secret in text:
                text = text.replace(secret, _REDACTED)

        # Apply regex patterns
        for pattern in self._secret_patterns:
            text = pattern.sub(self._replace_match, text)

        return text

    @staticmethod
    def _replace_match(match: re.Match) -> str:
        """Replacement function for re.sub.

        Preserves the key/label portion and masks only the secret value.
        """
        groups = match.groups()

        # Key-value patterns: group(1) = key+separator, group(2/3/4) = value
        if len(groups) >= 2 and groups[0] and groups[1] is not None:
            # Key-value style: keep the key, redact the value
            return f"{groups[0]}{_REDACTED}"

        # DB URL pattern: group(1) = prefix, group(2) = password, group(3) = @
        if len(groups) == 3 and groups[0] and groups[2]:
            return f"{groups[0]}{_REDACTED}{groups[2]}"

        # Standalone token patterns — redact the entire match
        return _REDACTED

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact a log record in-place.

        Args:
            record: The log record to process.

        Returns:
            Always True (the record is never dropped, only redacted).
        """
        # Redact the main message
        if record.getMessage():
            record.msg = self._redact_text(
                record.msg if isinstance(record.msg, str) else str(record.msg)
            )
            # Clear args so the message isn't re-formatted with stale values
            record.args = ()

        # Redact exc_info traceback if present and enabled
        if self.redact_traceback and record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            if exc_value and str(exc_value):
                # Create a new exception with redacted message
                redacted_msg = self._redact_text(str(exc_value))
                if redacted_msg != str(exc_value):
                    try:
                        new_exc = exc_type(redacted_msg)
                        new_exc.__cause__ = exc_value.__cause__
                        record.exc_info = (exc_type, new_exc, exc_tb)
                    except Exception:
                        # If we can't reconstruct the exception, leave as-is
                        pass

        return True


def add_redaction_filter_to_logger(
    logger: logging.Logger,
    redact_pii: bool = True,
) -> None:
    """Add the SecretRedactingFilter to a logger and all its handlers.

    This ensures the filter is applied at the logger level (before handlers
    process the record) and at each handler level.

    Args:
        logger: The logger to configure.
        redact_pii: If True, also redact PII data.
    """
    redaction_filter = SecretRedactingFilter(redact_pii=redact_pii)

    # Add filter to logger itself
    if not any(isinstance(f, SecretRedactingFilter) for f in logger.filters):
        logger.addFilter(redaction_filter)

    # Add filter to all existing handlers
    for handler in logger.handlers:
        if not any(isinstance(f, SecretRedactingFilter) for f in handler.filters):
            handler.addFilter(redaction_filter)


def redact_string(text: str) -> str:
    """Convenience function to redact a single string.

    Args:
        text: The string to redact.

    Returns:
        The redacted string.
    """
    filter_instance = SecretRedactingFilter()
    return filter_instance._redact_text(text)
