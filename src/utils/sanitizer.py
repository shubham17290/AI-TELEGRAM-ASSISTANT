"""Input sanitization and validation utilities.

Provides functions to sanitize and validate incoming request payloads and
parameters to prevent injection attacks (XSS, SQLi, NoSQLi) and other
malicious input patterns.

All sanitization functions follow a "safe by default" approach — they strip
or reject dangerous content rather than trying to allow-list safe content.
"""

import html
import re
import unicodedata
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum safe length for user input
MAX_MESSAGE_LENGTH = 4096
MAX_COMMAND_ARG_LENGTH = 1024

# Hard limit to reject massive payloads BEFORE any processing.
# This is a pre-sanitization guard to prevent memory exhaustion attacks.
MAX_RAW_PAYLOAD_LENGTH = 60000  # 60KB — far above Telegram's real limit

# Threshold above which consecutive whitespace is collapsed.
# Messages with run-on whitespace (e.g., massive indentation) are normalized.
MAX_CONSECUTIVE_WHITESPACE = 4

# Control characters to strip (excluding newlines and tabs which are normal)
_CONTROL_CHARS_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# SQL injection patterns (common keywords used in SQLi attempts)
_SQL_INJECTION_PATTERN = re.compile(
    r'(?i)(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|'
    r'EXEC|EXECUTE|UNION|LOAD_FILE|INTO\s+OUTFILE|INTO\s+DUMPFILE|'
    r'INFORMATION_SCHEMA|SLEEP|BENCHMARK|WAITFOR|DELAY|PG_SLEEP)\b)',
)

# NoSQL injection patterns (MongoDB operators)
_NOSQL_INJECTION_PATTERN = re.compile(
    r'(?i)(\$where|\$regex|\$ne|\$gt|\$lt|\$gte|\$lte|\$in|\$nin|\$exists|\$mod)',
)

# URL detection pattern
_URL_PATTERN = re.compile(
    r'(?i)\b(?:https?://|ftp://|www\.)[^\s\'"<>()\[\]{}]+',
)

# HTML tag detection pattern
_HTML_TAG_PATTERN = re.compile(r'<[^>]*>')


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a text string by stripping control characters, normalizing
    Unicode, and truncating to a safe length.

    This is the primary sanitization function for user messages. It does NOT
    escape HTML — that's done separately in ``escape_html()`` when the output
    is rendered in HTML context.

    Args:
        text: The raw input text to sanitize.
        max_length: Maximum allowed length. Defaults to ``MAX_MESSAGE_LENGTH``.

    Returns:
        The sanitized text string.
    """
    if not text or not isinstance(text, str):
        return ""

    max_length = max_length or MAX_MESSAGE_LENGTH

    # 0. Reject massive payloads early (memory exhaustion defense)
    if is_payload_too_large(text):
        # Truncate brutally to the max safe length and strip whitespace;
        # this prevents processing a multi-megabyte string in memory.
        text = text[:MAX_MESSAGE_LENGTH]

    # 1. Strip ASCII control characters (except \n, \r, \t)
    text = _CONTROL_CHARS_PATTERN.sub("", text)

    # 2. Normalize Unicode (NFKC: compatibility decomposition + canonical composition)
    # This prevents homoglyph attacks and normalises unicode
    text = unicodedata.normalize("NFKC", text)

    # 3. Collapse excessive consecutive whitespace (anti-spam / anti-abuse)
    text = normalize_whitespace(text)

    # 4. Truncate to safe length
    if len(text) > max_length:
        text = text[:max_length]

    return text


def is_payload_too_large(text: str, max_raw_length: Optional[int] = None) -> bool:
    """
    Check if a raw text payload exceeds the hard size guard.

    This is a pre-processing check used to reject massive payloads before
    they are loaded into memory or sent to the AI / database.

    Args:
        text: The raw input text.
        max_raw_length: Maximum allowed raw length (defaults to 60KB).

    Returns:
        True if the payload is too large and should be rejected, False otherwise.
    """
    if not text or not isinstance(text, str):
        return False
    limit = max_raw_length or MAX_RAW_PAYLOAD_LENGTH
    return len(text) > limit


def normalize_whitespace(text: str, max_consecutive: Optional[int] = None) -> str:
    """
    Collapse runs of consecutive whitespace characters to a single space.

    Telegram messages can contain a massive run of spaces/tabs/newlines,
    which wastes tokens, inflates DB storage, and can be used for spam.
    This function collapses runs longer than ``max_consecutive`` back to a
    single space.

    Args:
        text: The text to normalize.
        max_consecutive: Maximum allowed consecutive whitespace characters
            before collapsing (defaults to ``MAX_CONSECUTIVE_WHITESPACE``).

    Returns:
        The normalized text.
    """
    if not text:
        return text

    limit = max_consecutive or MAX_CONSECUTIVE_WHITESPACE
    if limit <= 0:
        return text

    # Regex that matches runs of ANY whitespace (space, tab, newline, etc.)
    # longer than the limit, and replaces them with a single space.
    pattern = re.compile(rf"(\s{{{limit},}})")
    return pattern.sub(" ", text)


def sanitize_command_argument(arg: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a single command argument (e.g., a page number or user ID).

    More restrictive than ``sanitize_text`` — strips HTML tags entirely
    and removes shell metacharacters.

    Args:
        arg: The raw command argument to sanitize.
        max_length: Maximum allowed length. Defaults to ``MAX_COMMAND_ARG_LENGTH``.

    Returns:
        The sanitized argument string.
    """
    if not arg or not isinstance(arg, str):
        return ""

    max_length = max_length or MAX_COMMAND_ARG_LENGTH

    # Run the base text sanitizer first
    arg = sanitize_text(arg, max_length)

    # Strip HTML tags
    arg = _HTML_TAG_PATTERN.sub("", arg)

    # Strip shell metacharacters for safety
    arg = arg.replace("`", "").replace("$", "").replace("|", "").replace(";", "")

    return arg


def escape_html(text: str) -> str:
    """
    Escape HTML entities in user input to prevent XSS attacks.

    This should be used for any user-generated content that is rendered
    in an HTML context (e.g., Telegram's ``reply_html``, ``parse_mode="HTML"``).

    Args:
        text: The text to escape.

    Returns:
        The HTML-escaped text.
    """
    if not text:
        return ""
    return html.escape(text, quote=True)


def contains_sql_injection(text: str) -> bool:
    """
    Check if text contains SQL injection patterns.

    This is a best-effort check and should NOT be relied upon as the sole
    SQL injection prevention mechanism. Parameterized queries (SQLAlchemy
    ORM) are the primary defense.

    Args:
        text: The text to check.

    Returns:
        True if SQL injection patterns are detected, False otherwise.
    """
    if not text:
        return False
    return bool(_SQL_INJECTION_PATTERN.search(text))


def contains_nosql_injection(text: str) -> bool:
    """
    Check if text contains NoSQL injection patterns (MongoDB operators).

    Args:
        text: The text to check.

    Returns:
        True if NoSQL injection patterns are detected, False otherwise.
    """
    if not text:
        return False
    return bool(_NOSQL_INJECTION_PATTERN.search(text))


def contains_malicious_patterns(text: str) -> bool:
    """
    Combined check for SQLi, NoSQLi, and other malicious patterns.

    Args:
        text: The text to check.

    Returns:
        True if any malicious patterns are detected, False otherwise.
    """
    return (
        contains_sql_injection(text)
        or contains_nosql_injection(text)
    )


def extract_urls(text: str) -> list[str]:
    """
    Extract all URLs from a text string.

    Args:
        text: The text to scan.

    Returns:
        List of detected URLs.
    """
    if not text:
        return []
    return _URL_PATTERN.findall(text)


def count_urls(text: str) -> int:
    """
    Count the number of URLs in a text string.

    Args:
        text: The text to scan.

    Returns:
        Number of URLs detected.
    """
    return len(extract_urls(text))


def validate_user_id(user_id: Optional[int]) -> bool:
    """
    Validate that a user ID is a positive integer.

    Args:
        user_id: The user ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    return user_id is not None and isinstance(user_id, int) and user_id > 0


def validate_chat_id(chat_id: Optional[int]) -> bool:
    """
    Validate that a chat ID is a non-zero integer.

    Args:
        chat_id: The chat ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    return chat_id is not None and isinstance(chat_id, int) and chat_id != 0
