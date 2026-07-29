"""Handlers package."""

from telegram.ext import CommandHandler, MessageHandler, filters

from src.handlers.admin_handlers import (
    broadcast_command,
    health_command,
    logs_command,
    restart_command,
    stats_command,
    users_command,
)
from src.handlers.command_handlers import (
    about_command,
    help_command,
    history_command,
    ping_command,
    settings_command,
    start_command,
    unknown_command,
)
from src.handlers.message_handler import register_message_handlers
from src.middlewares.wrapper import apply_middleware


def register_handlers(application) -> None:
    """
    Register all bot handlers with middleware.

    Args:
        application: Telegram bot application instance
    """
    # Register message handlers first (text messages)
    register_message_handlers(application)

    # Register admin command handlers with middleware
    application.add_handler(
        CommandHandler("stats", apply_middleware(stats_command))
    )
    application.add_handler(
        CommandHandler("users", apply_middleware(users_command))
    )
    application.add_handler(
        CommandHandler("broadcast", apply_middleware(broadcast_command))
    )
    application.add_handler(
        CommandHandler("logs", apply_middleware(logs_command))
    )
    application.add_handler(
        CommandHandler("restart", apply_middleware(restart_command))
    )
    application.add_handler(
        CommandHandler("health", apply_middleware(health_command))
    )

    # Register regular command handlers with middleware
    application.add_handler(
        CommandHandler("start", apply_middleware(start_command))
    )
    application.add_handler(
        CommandHandler("help", apply_middleware(help_command))
    )
    application.add_handler(
        CommandHandler("about", apply_middleware(about_command))
    )
    application.add_handler(
        CommandHandler("ping", apply_middleware(ping_command))
    )
    application.add_handler(
        CommandHandler("settings", apply_middleware(settings_command))
    )
    application.add_handler(
        CommandHandler("history", apply_middleware(history_command))
    )

    # Register unknown command handler with middleware (must be last)
    application.add_handler(
        MessageHandler(filters.COMMAND, apply_middleware(unknown_command))
    )
