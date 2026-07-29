"""Middleware registry and factory for the Telegram bot."""

from typing import Optional

from src.middlewares.auth import AuthMiddleware
from src.middlewares.exception_handler import ExceptionHandlerMiddleware
from src.middlewares.logging import LoggingMiddleware
from src.middlewares.rate_limit import RateLimitMiddleware
from src.middlewares.user_activity import UserActivityMiddleware
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MiddlewareRegistry:
    """
    Registry for managing and configuring middlewares.

    Provides a centralized way to create, configure, and access middlewares.
    """

    def __init__(self):
        """Initialize middleware registry."""
        self._middlewares: dict[str, object] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all default middlewares with configuration."""
        if self._initialized:
            logger.warning("Middleware registry already initialized")
            return

        # Create middlewares with configuration
        self._middlewares = {
            "logging": LoggingMiddleware(),
            "rate_limit": RateLimitMiddleware(),
            "exception_handler": ExceptionHandlerMiddleware(),
            "user_activity": UserActivityMiddleware(),
            "auth": AuthMiddleware(enabled=False),  # Disabled by default
        }

        self._initialized = True
        logger.info(
            f"Middleware registry initialized with {len(self._middlewares)} middlewares"
        )

    def get(self, name: str) -> Optional[object]:
        """
        Get a middleware by name.

        Args:
            name: Middleware name

        Returns:
            Middleware instance or None if not found
        """
        if not self._initialized:
            self.initialize()

        return self._middlewares.get(name)

    def get_all(self) -> dict[str, object]:
        """
        Get all registered middlewares.

        Returns:
            Dictionary of middleware name to middleware instance
        """
        if not self._initialized:
            self.initialize()

        return self._middlewares.copy()

    def get_default_chain(self) -> list[object]:
        """
        Get the default middleware chain in execution order.

        The order is important:
        1. Exception handler (innermost - catches all exceptions)
        2. Authentication (checks permissions)
        3. Rate limiter (prevents abuse)
        4. User activity (tracks interactions)
        5. Logging (outermost - logs everything)

        Returns:
            List of middlewares in execution order
        """
        if not self._initialized:
            self.initialize()

        # Return in reverse order (last middleware wraps first)
        return [
            self._middlewares["exception_handler"],
            self._middlewares["auth"],
            self._middlewares["rate_limit"],
            self._middlewares["user_activity"],
            self._middlewares["logging"],
        ]

    def register(self, name: str, middleware: object) -> None:
        """
        Register a custom middleware.

        Args:
            name: Middleware name
            middleware: Middleware instance
        """
        if not self._initialized:
            self.initialize()

        self._middlewares[name] = middleware
        logger.info(f"Custom middleware registered: {name}")

    def unregister(self, name: str) -> None:
        """
        Unregister a middleware.

        Args:
            name: Middleware name
        """
        if name in self._middlewares:
            del self._middlewares[name]
            logger.info(f"Middleware unregistered: {name}")

    def get_middleware(self, name: str) -> Optional[object]:
        """
        Alias for get() method.

        Args:
            name: Middleware name

        Returns:
            Middleware instance or None if not found
        """
        return self.get(name)

    def configure(self, name: str, **kwargs) -> None:
        """
        Configure a middleware with additional parameters.

        Note: This is a placeholder for future configuration logic.
        Most middlewares should be configured at initialization time.

        Args:
            name: Middleware name
            **kwargs: Configuration parameters
        """
        middleware = self.get(name)
        if middleware is None:
            logger.warning(f"Cannot configure non-existent middleware: {name}")
            return

        logger.info(f"Middleware '{name}' configuration updated: {kwargs}")


# Global registry instance
_registry: Optional[MiddlewareRegistry] = None


def get_registry() -> MiddlewareRegistry:
    """
    Get the global middleware registry instance.

    Returns:
        MiddlewareRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = MiddlewareRegistry()
        _registry.initialize()
    return _registry


def create_middleware_chain(include: Optional[list[str]] = None) -> list[object]:
    """
    Create a middleware chain with specified middlewares.

    Args:
        include: List of middleware names to include (None for all defaults)

    Returns:
        List of middleware instances in execution order
    """
    registry = get_registry()

    if include is None:
        return registry.get_default_chain()

    middlewares = []
    for name in include:
        middleware = registry.get(name)
        if middleware:
            middlewares.append(middleware)
        else:
            logger.warning(f"Middleware not found: {name}")

    return middlewares
