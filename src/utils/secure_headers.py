"""Secure HTTP client configuration and security headers utility.

Since this application is a Telegram bot (not a web server), this module
provides:

1. A configured HTTP client (httpx) with secure defaults — timeouts, TLS
   verification, safe redirect handling, and request size limits.
2. A dictionary of recommended HTTP security headers for any future web
   endpoints (health checks, webhooks, admin panels).
3. Utilities to configure the OpenAI HTTP client with secure defaults.

Usage:
    from src.utils.secure_headers import get_secure_http_client, SECURITY_HEADERS

    # Get a pre-configured secure HTTP client
    client = get_secure_http_client()
    response = await client.get("https://api.example.com")

    # Apply security headers to a web framework response (future use)
    response.headers.update(SECURITY_HEADERS)
"""

import ssl
from typing import Optional

import httpx


# ---------------------------------------------------------------------------
# Security Headers Dictionary
# These headers should be applied to any HTTP response served by this
# application. Currently unused (no web server), but ready for future use.
# ---------------------------------------------------------------------------

SECURITY_HEADERS: dict[str, str] = {
    # Prevents MIME-type sniffing
    "X-Content-Type-Options": "nosniff",
    # Prevents clickjacking
    "X-Frame-Options": "DENY",
    # Enables XSS filter in older browsers
    "X-XSS-Protection": "1; mode=block",
    # HSTS - force HTTPS for 1 year (31536000 seconds)
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # Referrer policy
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Content Security Policy — restrict resources to same origin
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    ),
    # Disable caching of sensitive data
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    # Permissions Policy — restrict browser features
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), "
        "interest-cohort=()"
    ),
}


# ---------------------------------------------------------------------------
# Secure HTTP Client Factory
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 30.0


def get_secure_http_client(
    timeout: Optional[float] = None,
    max_redirects: int = 5,
    verify_tls: Optional[bool] = None,
) -> httpx.AsyncClient:
    """
    Create an HTTPX async client with secure defaults.

    Args:
        timeout: Request timeout in seconds (defaults to ``API_TIMEOUT`` config).
        max_redirects: Maximum number of redirects to follow.
        verify_tls: Whether to verify TLS certificates. When ``None`` (default),
            TLS verification is ALWAYS enabled in production and enabled in
            development. Passing ``False`` explicitly in production is rejected
            for security reasons.

    Returns:
        Configured ``httpx.AsyncClient`` instance.

    Raises:
        ValueError: If ``verify_tls=False`` is requested in production.
    """
    # Load config for timeout and environment
    from src.config.settings import config

    if timeout is None:
        timeout = float(config.API_TIMEOUT)

    # TLS enforcement: in production, TLS verification is MANDATORY.
    # It can never be disabled — doing so would expose the bot to
    # man-in-the-middle attacks on API credentials.
    if verify_tls is None:
        verify_tls = True  # Always verify by default
    elif verify_tls is False and config.is_production:
        raise ValueError(
            "TLS certificate verification cannot be disabled in production "
            "environment. Refusing to create an insecure HTTP client."
        )

    limits = httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20,
        keepalive_expiry=30.0,
    )

    # Configure TLS — always use a secure SSL context when verification is on
    if verify_tls:
        tls = httpx.create_ssl_context()
    else:
        # Only reachable in development/testing — keep the client usable but
        # log a loud warning so developers know it is insecure.
        import logging
        logging.getLogger(__name__).warning(
            "Creating HTTP client with TLS verification DISABLED. "
            "This is only allowed outside production."
        )
        tls = False

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            timeout,
            connect=timeout,
            read=timeout,
            write=timeout,
            pool=timeout,
        ),
        limits=limits,
        verify=tls,
        follow_redirects=True,
        max_redirects=max_redirects,
        # Default headers for all requests
        headers={
            "User-Agent": "AI-Telegram-Assistant/1.0",
            "Accept": "application/json",
        },
    )

    return client


# ---------------------------------------------------------------------------
# Secure HTTP Client for OpenAI
# ---------------------------------------------------------------------------

def get_secure_openai_client_kwargs() -> dict:
    """
    Get secure configuration keyword arguments for the OpenAI client.

    These can be passed to ``openai.AsyncOpenAI(**kwargs)`` to override
    the default HTTP client with secure settings.

    Returns:
        Dictionary of kwargs for the OpenAI client constructor.
    """
    http_client = get_secure_http_client()
    return {
        "http_client": http_client,
    }
