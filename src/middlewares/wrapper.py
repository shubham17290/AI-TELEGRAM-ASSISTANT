"""Handler wrapper for applying middleware to Telegram bot handlers."""

from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from src.middlewares.base import MiddlewareChain
from src.middlewares.registry import get_registry
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MiddlewareHandlerWrapper:
    """
    Wraps handlers with middleware chain.

    This class provides a way to apply middleware to all handlers in the bot.
    """

    def __init__(self, middleware_names: list[str] | None = None):
        """
        Initialize middleware wrapper.

        Args:
            middleware_names: List of middleware names to apply (None for defaults)
        """
        self.middleware_names = middleware_names
        self._chain: MiddlewareChain | None = None

    def _get_chain(self) -> MiddlewareChain:
        """
        Get or create the middleware chain.

        Returns:
            MiddlewareChain instance
        """
        if self._chain is None:
            registry = get_registry()

            if self.middleware_names is None:
                middlewares = registry.get_default_chain()
            else:
                middlewares = [
                    registry.get(name)
                    for name in self.middleware_names
                    if registry.get(name) is not None
                ]

            self._chain = MiddlewareChain(middlewares)
            logger.info(
                f"Middleware chain created with {len(middlewares)} middlewares"
            )

        return self._chain

    async def wrap_handler(self, handler: Callable, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Wrap a handler with middleware chain.

        Args:
            handler: Original handler function
            update: Telegram update object
            context: Bot context

        Returns:
            Handler response
        """
        chain = self._get_chain()
        return await chain.process(update, context, handler)

    def wrap_sync_handler(self, handler: Callable) -> Callable:
        """
        Wrap a synchronous handler to work with async middleware.

        Args:
            handler: Original handler function

        Returns:
            Wrapped async handler
        """
        wrapper = self

        async def wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Convert sync handler to async
            async def async_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                # Run sync handler in executor to avoid blocking
                import asyncio
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, handler, update, context)

            return await wrapper.wrap_handler(async_handler, update, context)

        return wrapped_handler


# Global wrapper instance
_wrapper: MiddlewareHandlerWrapper | None = None


def get_middleware_wrapper(middleware_names: list[str] | None = None) -> MiddlewareHandlerWrapper:
    """
    Get the global middleware wrapper instance.

    Args:
        middleware_names: Optional list of middleware names to use

    Returns:
        MiddlewareHandlerWrapper instance
    """
    global _wrapper
    if _wrapper is None or middleware_names is not None:
        _wrapper = MiddlewareHandlerWrapper(middleware_names)
    return _wrapper


def apply_middleware(handler: Callable, middleware_names: list[str] | None = None) -> Callable:
    """
    Apply middleware chain to a handler.

    This is a convenience function for wrapping handlers with middleware.

    Args:
        handler: Handler function to wrap
        middleware_names: Optional list of middleware names (None for defaults)

    Returns:
        Wrapped handler
    """
    wrapper = get_middleware_wrapper(middleware_names)
    return wrapper.wrap_sync_handler(handler)
