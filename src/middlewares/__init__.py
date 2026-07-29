"""Middlewares package for the Telegram bot."""

from src.middlewares.auth import AuthMiddleware
from src.middlewares.base import BaseMiddleware, MiddlewareChain
from src.middlewares.exception_handler import ExceptionHandlerMiddleware
from src.middlewares.logging import LoggingMiddleware
from src.middlewares.rate_limit import RateLimitMiddleware
from src.middlewares.registry import (
    MiddlewareRegistry,
    create_middleware_chain,
    get_registry,
)
from src.middlewares.user_activity import UserActivityMiddleware

__all__ = [
    # Base classes
    "BaseMiddleware",
    "MiddlewareChain",
    # Middleware implementations
    "LoggingMiddleware",
    "RateLimitMiddleware",
    "ExceptionHandlerMiddleware",
    "UserActivityMiddleware",
    "AuthMiddleware",
    # Registry and factory
    "MiddlewareRegistry",
    "get_registry",
    "create_middleware_chain",
]
