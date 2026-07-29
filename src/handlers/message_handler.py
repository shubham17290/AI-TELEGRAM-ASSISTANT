"""Message handlers for the bot."""

import asyncio
import logging
import time
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from src.config.settings import config
from src.database.connection import get_session
from src.services.ai_service import get_ai_service, TokenUsage
from src.services.conversation_logger import ConversationLogger
from src.services.conversation_memory import get_conversation_memory

logger = logging.getLogger(__name__)


# Default system prompt
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, friendly, and knowledgeable AI assistant. "
    "You provide clear, accurate, and concise responses. "
    "You maintain context from the conversation to provide relevant answers. "
    "If you don't know something, you say so honestly."
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming text messages with AI response.

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    user_message = update.message.text

    logger.info(f"User {user_id} sent message: {user_message[:50]}...")

    # Initialize services
    ai_service = get_ai_service()
    conversation_memory = get_conversation_memory()

    # Set default system prompt if not already set
    if not conversation_memory.get_system_prompt(user_id):
        conversation_memory.set_system_prompt(user_id, DEFAULT_SYSTEM_PROMPT)

    # Send initial "typing" message
    status_message = await update.message.reply_text("🤔 Thinking...")

    # Log user message to database
    async with get_session() as session:
        conversation_logger = ConversationLogger(session)
        await conversation_logger.log_user_message(
            user_id=user_id,
            content=user_message,
            chat_id=chat_id,
        )

    try:
        # Generate response with streaming
        full_response = ""
        last_update_time = time.time()
        update_interval = 1.5  # Update every 1.5 seconds to avoid rate limits

        async for chunk in ai_service.generate_response_stream(user_id, user_message):
            full_response += chunk

            # Batch updates to avoid hitting Telegram rate limits
            current_time = time.time()
            if current_time - last_update_time >= update_interval:
                try:
                    await status_message.edit_text(full_response + " ▌")
                    last_update_time = current_time
                except Exception as e:
                    # Ignore rate limit errors during streaming
                    if "429" not in str(e):
                        logger.warning(f"Failed to update message: {e}")

        # Final update with complete response
        try:
            await status_message.edit_text(full_response)
        except Exception as e:
            logger.warning(f"Failed to update final message: {e}")
            # If edit fails, send as new message
            await update.message.reply_text(full_response)

        # Log assistant response to database
        async with get_session() as session:
            conversation_logger = ConversationLogger(session)
            await conversation_logger.log_assistant_message(
                user_id=user_id,
                content=full_response,
                chat_id=chat_id,
            )

        logger.info(f"Sent response to user {user_id}: {full_response[:50]}...")

    except Exception as e:
        logger.error(f"Error handling message from user {user_id}: {e}", exc_info=True)

        # Send user-friendly error message
        error_message = (
            "😔 Sorry, I encountered an error while processing your request. "
            "Please try again in a moment."
        )

        try:
            await status_message.edit_text(error_message)
        except Exception:
            await update.message.reply_text(error_message)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle photo messages (placeholder for future image support).

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    logger.info(f"User {user.id} sent a photo (not yet supported)")

    await update.message.reply_text(
        "📸 Photo messages are not yet supported. "
        "Please send text messages only for now."
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle voice messages (placeholder for future voice support).

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    logger.info(f"User {user.id} sent a voice message (not yet supported)")

    await update.message.reply_text(
        "🎤 Voice messages are not yet supported. "
        "Please send text messages only for now."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle document messages (placeholder for future document support).

    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    logger.info(f"User {user.id} sent a document (not yet supported)")

    await update.message.reply_text(
        "📄 Document messages are not yet supported. "
        "Please send text messages only for now."
    )


def register_message_handlers(application) -> None:
    """
    Register all message handlers.

    Args:
        application: Telegram bot application instance
    """
    # Text message handler (must be registered before command handlers for proper routing)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Media handlers (optional, for future expansion)
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
