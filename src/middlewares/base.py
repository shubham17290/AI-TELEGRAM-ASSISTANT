"""Base middleware class for the Telegram bot."""

from abc import ABC, abstractmethod
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes


class BaseMiddleware(ABC):
    """Abstract base class for all middlewares."""

    @abstractmethod
    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable
    ):
        """
        Process the update through the middleware.

        Args:
            update: Telegram update object
            context: Bot context
            next_handler: Next handler in the chain

        Returns:
            Handler response
        """
        pass


class MiddlewareChain:
    """Chain multiple middlewares together."""

    def __init__(self, middlewares: list[BaseMiddleware]):
        """
        Initialize middleware chain.

        Args:
            middlewares: List of middlewares to apply in order
        """
        self.middlewares = middlewares

    async def process(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, final_handler: Callable
    ):
        """
        Process update through all middlewares.

        Args:
            update: Telegram update object
            context: Bot context
            final_handler: The final handler to execute

        Returns:
            Handler response
        """
        # Build the chain from last to first
        handler = final_handler
        for middleware in reversed(self.middlewares):
            handler = self._wrap_handler(middleware, handler)

        return await handler(update, context)

    def _wrap_handler(self, middleware: BaseMiddleware, handler: Callable) -> Callable:
        """
        Wrap a handler with a middleware.

        Args:
            middleware: Middleware to wrap with
            handler: Handler to wrap

        Returns:
            Wrapped handler
        """
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            return await middleware(update, context, handler)

        return wrapped
