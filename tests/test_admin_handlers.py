"""Tests for admin handlers."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update, User
from telegram.ext import ContextTypes

pytestmark = pytest.mark.asyncio

from src.handlers.admin_handlers import admin_only, BOT_START_TIME


class TestAdminOnlyDecorator:
    """Test the admin_only decorator."""

    @pytest.mark.asyncio
    async def test_admin_access_granted(self):
        """Test that admin user can access decorated function."""
        # Create mock update with admin user
        mock_user = MagicMock(spec=User)
        mock_user.id = 12345
        mock_user.username = "admin_user"

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Create a test handler
        @admin_only
        async def test_handler(update, context):
            return "success"

        # Mock config
        with patch('src.handlers.admin_handlers.config') as mock_config:
            mock_config.ADMIN_TELEGRAM_ID = 12345

            result = await test_handler(mock_update, mock_context)

            assert result == "success"
            mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_admin_access_denied(self):
        """Test that non-admin user is denied access."""
        # Create mock update with non-admin user
        mock_user = MagicMock(spec=User)
        mock_user.id = 99999
        mock_user.username = "regular_user"

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Create a test handler
        @admin_only
        async def test_handler(update, context):
            return "success"

        # Mock config
        with patch('src.handlers.admin_handlers.config') as mock_config:
            mock_config.ADMIN_TELEGRAM_ID = 12345

            result = await test_handler(mock_update, mock_context)

            assert result is None
            mock_update.message.reply_text.assert_called_once_with(
                "⛔ Permission Denied: Admin access required."
            )

    @pytest.mark.asyncio
    async def test_admin_not_configured(self):
        """Test behavior when admin ID is not configured."""
        # Create mock update
        mock_user = MagicMock(spec=User)
        mock_user.id = 12345

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Create a test handler
        @admin_only
        async def test_handler(update, context):
            return "success"

        # Mock config without ADMIN_TELEGRAM_ID
        with patch('src.handlers.admin_handlers.config') as mock_config:
            mock_config.ADMIN_TELEGRAM_ID = None

            result = await test_handler(mock_update, mock_context)

            assert result is None
            mock_update.message.reply_text.assert_called_once_with(
                "❌ Admin access not configured."
            )


class TestAdminCommands:
    """Test admin command handlers."""

    @pytest.mark.asyncio
    async def test_stats_command(self):
        """Test /stats command."""
        from src.handlers.admin_handlers import stats_command

        mock_user = MagicMock(spec=User)
        mock_user.id = 12345

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_html = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Mock config and database
        with patch('src.handlers.admin_handlers.config') as mock_config, \
             patch('src.handlers.admin_handlers.get_session') as mock_get_session:

            mock_config.ADMIN_TELEGRAM_ID = 12345

            # Mock database session
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

            # Mock repository results
            mock_session.execute = AsyncMock()
            mock_session.execute.return_value.scalar_one = MagicMock(return_value=100)
            mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=50)
            mock_session.execute.return_value.all = MagicMock(return_value=[])

            await stats_command(mock_update, mock_context)

            mock_update.message.reply_html.assert_called_once()
            response = mock_update.message.reply_html.call_args[0][0]
            assert "Bot Statistics" in response

    @pytest.mark.asyncio
    async def test_users_command(self):
        """Test /users command."""
        from src.handlers.admin_handlers import users_command

        mock_user = MagicMock(spec=User)
        mock_user.id = 12345

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_html = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        with patch('src.handlers.admin_handlers.config') as mock_config, \
             patch('src.handlers.admin_handlers.get_session') as mock_get_session:

            mock_config.ADMIN_TELEGRAM_ID = 12345

            # Mock database session
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

            # Mock repository
            mock_user_repo = MagicMock()
            mock_user_repo.count = AsyncMock(return_value=150)
            mock_user_repo.get_active_users = AsyncMock(return_value=[])

            with patch('src.handlers.admin_handlers.UserRepository', return_value=mock_user_repo):
                await users_command(mock_update, mock_context)

            mock_update.message.reply_html.assert_called_once()
            response = mock_update.message.reply_html.call_args[0][0]
            assert "User Statistics" in response
            assert "150" in response

    @pytest.mark.asyncio
    async def test_health_command(self):
        """Test /health command."""
        from src.handlers.admin_handlers import health_command

        mock_user = MagicMock(spec=User)
        mock_user.id = 12345

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_html = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        with patch('src.handlers.admin_handlers.config') as mock_config, \
             patch('src.handlers.admin_handlers.get_session') as mock_get_session, \
             patch('src.handlers.admin_handlers.psutil') as mock_psutil:

            mock_config.ADMIN_TELEGRAM_ID = 12345

            # Mock database session
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.execute = AsyncMock()

            # Mock psutil
            mock_psutil.cpu_percent = MagicMock(return_value=25.5)
            mock_memory = MagicMock()
            mock_memory.percent = 60.0
            mock_memory.used = 8589934592  # 8 GB
            mock_memory.total = 17179869184  # 16 GB
            mock_psutil.virtual_memory = MagicMock(return_value=mock_memory)

            mock_disk = MagicMock()
            mock_disk.percent = 45.0
            mock_disk.used = 500000000000  # 500 GB
            mock_disk.total = 1000000000000  # 1 TB
            mock_psutil.disk_usage = MagicMock(return_value=mock_disk)

            await health_command(mock_update, mock_context)

            mock_update.message.reply_html.assert_called_once()
            response = mock_update.message.reply_html.call_args[0][0]
            assert "System Health Status" in response
            assert "CPU" in response
            assert "RAM" in response

    @pytest.mark.asyncio
    async def test_logs_command(self):
        """Test /logs command."""
        from src.handlers.admin_handlers import logs_command

        mock_user = MagicMock(spec=User)
        mock_user.id = 12345

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_html = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        with patch('src.handlers.admin_handlers.config') as mock_config:
            mock_config.ADMIN_TELEGRAM_ID = 12345
            mock_config.log_file_path = Path("logs/app_development.log")

            # Create a temporary log file
            Path("logs").mkdir(exist_ok=True)
            test_log = Path("logs/app_development.log")
            test_log.write_text("Test log line 1\nTest log line 2\nTest log line 3\n")

            try:
                await logs_command(mock_update, mock_context)

                mock_update.message.reply_html.assert_called_once()
                response = mock_update.message.reply_html.call_args[0][0]
                assert "Last 3 lines from logs" in response
            finally:
                # Clean up
                if test_log.exists():
                    test_log.unlink()

    @pytest.mark.asyncio
    async def test_broadcast_command(self):
        """Test /broadcast command."""
        from src.handlers.admin_handlers import broadcast_command

        mock_user = MagicMock(spec=User)
        mock_user.id = 12345

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_context.args = ["Test", "broadcast", "message"]

        with patch('src.handlers.admin_handlers.config') as mock_config:
            mock_config.ADMIN_TELEGRAM_ID = 12345

            await broadcast_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            response = mock_update.message.reply_text.call_args[0][0]
            assert "Broadcast Preview" in response
            assert "Test broadcast message" in response

    @pytest.mark.asyncio
    async def test_broadcast_command_no_args(self):
        """Test /broadcast command without arguments."""
        from src.handlers.admin_handlers import broadcast_command

        mock_user = MagicMock(spec=User)
        mock_user.id = 12345

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_context.args = []

        with patch('src.handlers.admin_handlers.config') as mock_config:
            mock_config.ADMIN_TELEGRAM_ID = 12345

            await broadcast_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            response = mock_update.message.reply_text.call_args[0][0]
            assert "Usage: /broadcast <message>" in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
