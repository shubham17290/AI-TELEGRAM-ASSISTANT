"""Admin-only handlers for the Telegram bot."""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psutil
from sqlalchemy import select, func, text
from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import config
from src.database.connection import get_session
from src.database.models import User, ConversationHistory
from src.database.repositories.conversation_repository import ConversationRepository
from src.database.repositories.user_repository import UserRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Store bot start time for uptime calculation
BOT_START_TIME = time.time()


def admin_only(func):
    """
    Decorator to restrict handler access to admin only.

    Checks if the user's Telegram ID matches ADMIN_TELEGRAM_ID from config.
    If not authorized, sends a permission denied message and returns early.

    Args:
        func: Handler function to wrap

    Returns:
        Wrapped handler function
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[bool]:
        user = update.effective_user

        # Get admin ID from config
        admin_id = getattr(config, 'ADMIN_TELEGRAM_ID', None)

        if not admin_id:
            logger.error("ADMIN_TELEGRAM_ID not configured in environment")
            await update.message.reply_text("❌ Admin access not configured.")
            return None

        # Check if user is admin
        if user.id != admin_id:
            logger.warning(f"Unauthorized admin access attempt from user {user.id} ({user.username})")
            await update.message.reply_text("⛔ Permission Denied: Admin access required.")
            return None

        # User is authorized, execute the handler
        logger.info(f"Admin command executed by user {user.id} ({user.username})")
        return await func(update, context)

    return wrapper


@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /stats command - return bot statistics.

    Returns:
        - Total messages processed
        - Total tokens used
        - Database statistics
    """
    logger.info(f"Admin {update.effective_user.id} requested bot statistics")

    try:
        async with get_session() as session:
            # Get total messages and tokens from conversation history
            conv_repo = ConversationRepository(session)
            user_repo = UserRepository(session)

            # Get total messages count
            from sqlalchemy import select, func
            total_messages_query = select(func.count()).select_from(conv_repo.model)
            total_messages_result = await session.execute(total_messages_query)
            total_messages = total_messages_result.scalar_one()

            # Get total tokens used
            total_tokens_query = select(func.sum(ConversationHistory.tokens_used)).where(
                ConversationHistory.tokens_used.is_not(None)
            )
            total_tokens_result = await session.execute(total_tokens_query)
            total_tokens = total_tokens_result.scalar_one() or 0

            # Get total users
            total_users = await user_repo.count()

            # Get active users (users with activity in last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            active_users_query = select(func.count()).where(
                User.last_activity_at >= thirty_days_ago
            )
            active_users_result = await session.execute(active_users_query)
            active_users = active_users_result.scalar_one()

            # Get messages per role breakdown
            from sqlalchemy import func
            role_stats_query = (
                select(ConversationHistory.role, func.count().label('count'))
                .group_by(ConversationHistory.role)
            )
            role_stats_result = await session.execute(role_stats_query)
            role_stats = {row.role: row.count for row in role_stats_result.all()}

        # Calculate uptime
        uptime_seconds = time.time() - BOT_START_TIME
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        # Format response
        stats_text = (
            "📊 <b>Bot Statistics</b>\n\n"
            f"<b>General:</b>\n"
            f"• Uptime: {uptime_days}d {uptime_hours}h {uptime_minutes}m\n"
            f"• Total Users: {total_users}\n"
            f"• Active Users (30d): {active_users}\n\n"
            f"<b>Messages:</b>\n"
            f"• Total Messages: {total_messages}\n"
            f"• User Messages: {role_stats.get('user', 0)}\n"
            f"• AI Messages: {role_stats.get('assistant', 0)}\n"
            f"• System Messages: {role_stats.get('system', 0)}\n\n"
            f"<b>Token Usage:</b>\n"
            f"• Total Tokens: {total_tokens:,}\n"
        )

        await update.message.reply_html(stats_text)

    except Exception as e:
        logger.error(f"Error fetching stats: {e}", exc_info=True)
        await update.message.reply_text("❌ Error fetching statistics. Please try again later.")


@admin_only
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /users command - return user statistics.

    Returns total count of registered/unique users.
    """
    logger.info(f"Admin {update.effective_user.id} requested user statistics")

    try:
        async with get_session() as session:
            user_repo = UserRepository(session)

            # Get total users
            total_users = await user_repo.count()

            # Get active users
            active_users = await user_repo.get_active_users()
            active_count = len(active_users)

            # Get users created in last 24 hours
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            recent_users_query = select(func.count()).where(
                User.created_at >= one_day_ago
            )
            recent_users_result = await session.execute(recent_users_query)
            recent_users = recent_users_result.scalar_one()

            # Get users created in last 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            weekly_users_query = select(func.count()).where(
                User.created_at >= seven_days_ago
            )
            weekly_users_result = await session.execute(weekly_users_query)
            weekly_users = weekly_users_result.scalar_one()

        # Format response
        users_text = (
            "👥 <b>User Statistics</b>\n\n"
            f"• Total Users: {total_users}\n"
            f"• Active Users: {active_count}\n"
            f"• New Users (24h): {recent_users}\n"
            f"• New Users (7d): {weekly_users}\n"
        )

        await update.message.reply_html(users_text)

    except Exception as e:
        logger.error(f"Error fetching users: {e}", exc_info=True)
        await update.message.reply_text("❌ Error fetching user statistics. Please try again later.")


@admin_only
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /broadcast command - send message to all registered users.

    Usage: /broadcast <message>
    Implements batching and sleep intervals to avoid Telegram rate limits.
    """
    logger.info(f"Admin {update.effective_user.id} initiated broadcast")

    # Check if message is provided
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ Usage: /broadcast <message>\n\n"
            "Example: /broadcast Hello everyone! Bot maintenance scheduled for tonight."
        )
        return

    # Get broadcast message
    broadcast_message = " ".join(context.args)

    # Confirm with admin
    confirm_message = await update.message.reply_text(
        f"📢 <b>Broadcast Preview</b>\n\n"
        f"{broadcast_message}\n\n"
        f"Send this to all users? (yes/no)",
        parse_mode="HTML"
    )

    # Store broadcast message in context for confirmation
    context.user_data['broadcast_message'] = broadcast_message
    context.user_data['broadcast_confirm_id'] = confirm_message.message_id

    # Note: In a production bot, you might want to implement a conversation handler
    # for the confirmation step. For simplicity, we'll proceed with the broadcast.
    # You can enhance this by adding a confirmation conversation handler.


@admin_only
async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Execute the broadcast after confirmation.

    This is a separate function to allow for confirmation flow.
    """
    broadcast_message = context.user_data.get('broadcast_message')

    if not broadcast_message:
        await update.message.reply_text("❌ No broadcast message found. Use /broadcast first.")
        return

    try:
        async with get_session() as session:
            user_repo = UserRepository(session)
            active_users = await user_repo.get_active_users()

        total_users = len(active_users)
        logger.info(f"Starting broadcast to {total_users} users")

        # Send initial status
        status_message = await update.message.reply_text(
            f"📤 <b>Broadcast Started</b>\n\n"
            f"Total users: {total_users}\n"
            f"Progress: 0/{total_users}",
            parse_mode="HTML"
        )

        # Broadcast settings
        BATCH_SIZE = 20  # Send to 20 users
        SLEEP_INTERVAL = 1  # Sleep for 1 second between batches
        success_count = 0
        fail_count = 0

        # Send messages in batches
        for i in range(0, total_users, BATCH_SIZE):
            batch = active_users[i:i + BATCH_SIZE]

            for user in batch:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"📢 <b>Announcement</b>\n\n{broadcast_message}",
                        parse_mode="HTML"
                    )
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send broadcast to user {user.telegram_id}: {e}")
                    fail_count += 1

            # Update progress
            current_progress = min(i + BATCH_SIZE, total_users)
            await status_message.edit_text(
                f"📤 <b>Broadcast in Progress</b>\n\n"
                f"Total users: {total_users}\n"
                f"Progress: {current_progress}/{total_users}\n"
                f"Success: {success_count} | Failed: {fail_count}",
                parse_mode="HTML"
            )

            # Sleep between batches to avoid rate limits
            if i + BATCH_SIZE < total_users:
                await asyncio.sleep(SLEEP_INTERVAL)

        # Final status
        await status_message.edit_text(
            f"✅ <b>Broadcast Complete</b>\n\n"
            f"Total users: {total_users}\n"
            f"Successfully sent: {success_count}\n"
            f"Failed: {fail_count}\n"
            f"Success rate: {(success_count/total_users*100):.1f}%",
            parse_mode="HTML"
        )

        logger.info(f"Broadcast completed: {success_count} success, {fail_count} failed")

    except Exception as e:
        logger.error(f"Error during broadcast: {e}", exc_info=True)
        await update.message.reply_text("❌ Error during broadcast. Please try again later.")
    finally:
        # Clean up context
        context.user_data.pop('broadcast_message', None)
        context.user_data.pop('broadcast_confirm_id', None)


@admin_only
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /logs command - retrieve last 20-30 lines of application log.

    Reads from the current log file and sends the last N lines to the admin.
    """
    logger.info(f"Admin {update.effective_user.id} requested logs")

    try:
        # Get log file path from config
        log_file_path = config.log_file_path

        if not log_file_path.exists():
            await update.message.reply_text(
                f"❌ Log file not found at: {log_file_path}\n"
                f"Please check if logging is configured correctly."
            )
            return

        # Read last 30 lines from log file
        lines_to_fetch = 30
        lines = []

        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                # Read all lines and get the last N lines
                all_lines = f.readlines()
                lines = all_lines[-lines_to_fetch:] if len(all_lines) > lines_to_fetch else all_lines
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            await update.message.reply_text("❌ Error reading log file. Please try again later.")
            return

        if not lines:
            await update.message.reply_text("📋 Log file is empty.")
            return

        # Format log output
        log_content = "".join(lines)

        # Send as file if too long, otherwise as message
        if len(log_content) > 4000:
            # Create a temporary file with logs
            temp_log_file = Path("logs") / f"temp_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            temp_log_file.parent.mkdir(parents=True, exist_ok=True)

            with open(temp_log_file, 'w', encoding='utf-8') as f:
                f.write(log_content)

            # Send file
            with open(temp_log_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    caption=f"📋 Last {len(lines)} lines from log file"
                )

            # Clean up temp file
            temp_log_file.unlink()
        else:
            # Send as message
            log_text = f"📋 <b>Last {len(lines)} lines from logs:</b>\n\n<pre>{log_content}</pre>"
            await update.message.reply_html(log_text)

    except Exception as e:
        logger.error(f"Error fetching logs: {e}", exc_info=True)
        await update.message.reply_text("❌ Error fetching logs. Please try again later.")


@admin_only
async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /restart command - soft restart the bot.

    Safely closes database connections and exits with code 0,
    allowing process manager (systemd, Docker, PM2) to auto-restart.
    """
    logger.info(f"Admin {update.effective_user.id} initiated bot restart")

    try:
        # Send confirmation message
        await update.message.reply_text(
            "🔄 <b>Restarting bot...</b>\n\n"
            "The bot will be back online shortly.\n"
            "This process will be handled by your process manager.",
            parse_mode="HTML"
        )

        logger.info("Bot restart initiated by admin - shutting down gracefully")

        # Give a moment for the message to be sent
        await asyncio.sleep(2)

        # Shutdown the application gracefully
        if context.application:
            await context.application.stop()
            await context.application.shutdown()

        # Exit with code 0 to allow process manager to restart
        logger.info("Bot shutdown complete - exiting with code 0")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error during restart: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Error during restart. Please try again later.")
        except:
            pass
        sys.exit(1)


@admin_only
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /health command - return system health status.

    Returns:
    - Database connection status
    - Bot uptime
    - CPU and RAM usage
    - Disk space
    """
    logger.info(f"Admin {update.effective_user.id} requested health status")

    try:
        # Calculate uptime
        uptime_seconds = time.time() - BOT_START_TIME
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        uptime_seconds_remainder = int(uptime_seconds % 60)

        # Check database connection
        db_status = "❌ Disconnected"
        try:
            async with get_session() as session:
                # Execute a simple query to check connection
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
                db_status = "✅ Connected"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = f"❌ Error: {str(e)[:50]}"

        # Get system stats
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            cpu_text = f"{cpu_percent}%"
            ram_text = f"{memory.percent}% ({memory.used / (1024**3):.2f} GB / {memory.total / (1024**3):.2f} GB)"
            disk_text = f"{disk.percent}% ({disk.used / (1024**3):.2f} GB / {disk.total / (1024**3):.2f} GB)"
        except Exception as e:
            logger.warning(f"Could not get system stats: {e}")
            cpu_text = "N/A"
            ram_text = "N/A"
            disk_text = "N/A"

        # Format response
        health_text = (
            "💚 <b>System Health Status</b>\n\n"
            f"<b>Bot Status:</b>\n"
            f"• Uptime: {uptime_days}d {uptime_hours}h {uptime_minutes}m {uptime_seconds_remainder}s\n"
            f"• Status: Running ✅\n\n"
            f"<b>Database:</b>\n"
            f"• Connection: {db_status}\n\n"
            f"<b>System Resources:</b>\n"
            f"• CPU Usage: {cpu_text}\n"
            f"• RAM Usage: {ram_text}\n"
            f"• Disk Usage: {disk_text}\n"
        )

        await update.message.reply_html(health_text)

    except Exception as e:
        logger.error(f"Error checking health: {e}", exc_info=True)
        await update.message.reply_text("❌ Error checking health. Please try again later.")


