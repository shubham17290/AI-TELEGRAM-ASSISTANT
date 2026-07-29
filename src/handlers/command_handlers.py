"""Command handlers for the Telegram bot."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.database.connection import get_session
from src.services.conversation_logger import ConversationLogger

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")

    welcome_message = (
        f"Hello {user.mention_html()}! 👋\n\n"
        "Welcome to AI Telegram Assistant.\n"
        "I'm here to help you. Use /help to see available commands."
    )

    await update.message.reply_html(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command.

    Args:
        update: Telegram update object
        context: Bot context
    """
    logger.info(f"User {update.effective_user.id} requested help")

    help_text = (
        "📚 <b>Available Commands:</b>\n\n"
        "/start - Start the bot and get welcome message\n"
        "/help - Show this help message\n"
        "/about - Information about this bot\n"
        "/ping - Check bot latency\n"
        "/settings - Configure your preferences\n\n"
        "💡 Just send me a message and I'll respond!"
    )

    await update.message.reply_html(help_text)


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /about command.

    Args:
        update: Telegram update object
        context: Bot context
    """
    logger.info(f"User {update.effective_user.id} requested about info")

    about_text = (
        "🤖 <b>AI Telegram Assistant</b>\n\n"
        "Version: 1.0.0\n"
        "A powerful Telegram bot built with python-telegram-bot.\n\n"
        "Features:\n"
        "• Fast and responsive\n"
        "• Async architecture\n"
        "• Easy to use\n\n"
        "Built with ❤️ using python-telegram-bot"
    )

    await update.message.reply_html(about_text)


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /ping command - check bot latency.

    Args:
        update: Telegram update object
        context: Bot context
    """
    logger.info(f"User {update.effective_user.id} pinged the bot")

    # Calculate latency
    start_time = update.message.date.timestamp()

    ping_message = await update.message.reply_text("🏓 Pong!")

    # Calculate round-trip time
    end_time = ping_message.date.timestamp()
    latency = (end_time - start_time) * 1000  # Convert to milliseconds

    await ping_message.edit_text(f"🏓 Pong!\n⏱️ Latency: {latency:.2f}ms")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /settings command.

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    logger.info(f"User {user.id} accessed settings")

    settings_text = (
        "⚙️ <b>Settings</b>\n\n"
        "Here you can configure your preferences.\n\n"
        "Available settings:\n"
        "• Language: English\n"
        "• Notifications: Enabled\n\n"
        "More settings coming soon!"
    )

    await update.message.reply_html(settings_text)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle unknown commands.

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    command = update.message.text.split()[0] if update.message.text else "/unknown"

    logger.info(f"User {user.id} sent unknown command: {command}")

    response = (
        f"❓ Unknown command: {command}\n\n"
        "Use /help to see available commands."
    )

    await update.message.reply_text(response)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /history command - show paginated conversation history.

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id

    logger.info(f"User {user_id} requested conversation history")

    # Parse page number from command arguments
    page = 1
    if context.args and len(context.args) > 0:
        try:
            page = int(context.args[0])
            if page < 1:
                page = 1
        except (ValueError, IndexError):
            page = 1

    page_size = 5  # Show 5 messages per page

    # Fetch paginated history from database
    async with get_session() as session:
        conversation_logger = ConversationLogger(session)
        records, total_count = await conversation_logger.get_user_history_paginated(
            user_id=user_id, page=page, page_size=page_size
        )

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    # Format response
    if not records:
        response = (
            "📭 <b>No conversation history yet</b>\n\n"
            "Start chatting to build your history!"
        )
    else:
        response = f"📜 <b>Conversation History</b> (Page {page}/{total_pages})\n\n"

        for idx, record in enumerate(records, 1):
            # Format timestamp
            timestamp = record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "Unknown"

            # Truncate long messages
            content = record.content
            if len(content) > 100:
                content = content[:97] + "..."

            # Add role indicator
            role_emoji = "👤" if record.role == "user" else "🤖"
            role_name = "You" if record.role == "user" else "AI"

            response += (
                f"{idx}. {role_emoji} <b>{role_name}</b> ({timestamp})\n"
                f"   {content}\n\n"
            )

        # Add pagination info
        if total_pages > 1:
            response += f"📄 Page {page} of {total_pages} | Total messages: {total_count}\n"
            response += "Use /history <page_number> to see more"

    await update.message.reply_html(response)
