"""Main entry point for the AI Telegram Assistant bot."""

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import Optional

from telegram.ext import ApplicationBuilder

from src.config.settings import config
from src.database.initialization import initialize_database
from src.handlers import register_handlers
from src.middlewares import get_registry
from src.services.ai_service import TokenUsage
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Global application instance for graceful shutdown
_application: Optional[ApplicationBuilder] = None


async def post_init(application) -> None:
    """
    Post-initialization callback.

    Args:
        application: Telegram bot application instance
    """
    logger.info("Bot initialized successfully!")
    logger.info(f"Bot username: @{(await application.bot.get_me()).username}")
    logger.info("Starting polling...")


async def post_shutdown(application) -> None:
    """
    Post-shutdown callback.

    Args:
        application: Telegram bot application instance
    """
    logger.info("Bot shutdown complete!")


async def shutdown(application) -> None:
    """
    Gracefully shutdown the bot.

    Args:
        application: Telegram bot application instance
    """
    logger.info("Initiating graceful shutdown...")

    try:
        # Stop the bot
        await application.stop()
        logger.info("Bot stopped successfully")

        # Shutdown the application
        await application.shutdown()
        logger.info("Bot shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


def handle_signal(signum, frame, application) -> None:
    """
    Handle system signals for graceful shutdown.

    Args:
        signum: Signal number
        frame: Current stack frame
        application: Telegram bot application instance
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal")

    # Create a new event loop for shutdown if needed
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # Schedule shutdown in the running loop
            loop.create_task(shutdown(application))
        else:
            # Run shutdown in the current loop
            loop.run_until_complete(shutdown(application))
    except RuntimeError:
        # No event loop running, create one
        asyncio.run(shutdown(application))


async def main() -> None:
    """Initialize and run the bot."""
    global _application

    # Setup logging
    setup_logger()
    logger.info("Initializing bot...")

    # Validate configuration
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

    # Perform strict startup validation of all secrets and settings
    try:
        startup_warnings = config.validate_startup()
        for warning_msg in startup_warnings:
            logger.warning(f"Startup warning: {warning_msg}")
        logger.info("Startup validation passed successfully")
    except Exception as e:
        logger.error(f"Startup validation failed: {e}")
        raise

    try:
        # Initialize database
        logger.info("Initializing database...")
        await initialize_database()
        logger.info("Database initialized successfully!")

        # Build application
        application = (
            ApplicationBuilder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .post_init(post_init)
            .post_shutdown(post_shutdown)
            .build()
        )

        _application = application

        # Initialize middleware registry
        middleware_registry = get_registry()
        middleware_registry.initialize()
        logger.info(
            f"Middleware system initialized with {len(middleware_registry.get_all())} middlewares"
        )

        # Register handlers
        register_handlers(application)

        # Log token usage summary periodically
        logger.info("Bot is ready to process messages with OpenAI integration")

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, lambda s, f: handle_signal(s, f, application))
        signal.signal(signal.SIGTERM, lambda s, f: handle_signal(s, f, application))

        # Start polling
        logger.info("Bot started successfully!")
        await application.run_polling()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await shutdown(application)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        exit(1)
