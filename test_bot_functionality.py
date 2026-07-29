"""Test script to validate bot functionality without running the full bot."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_configuration():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("TEST 1: Configuration Loading")
    print("="*60)

    try:
        from src.config.settings import get_config

        config = get_config()

        # Verify required fields
        assert config.TELEGRAM_BOT_TOKEN, "TELEGRAM_BOT_TOKEN is required"
        assert config.OPENAI_API_KEY, "OPENAI_API_KEY is required"
        assert config.AI_PROVIDER == "openai", "AI_PROVIDER should be 'openai'"
        assert config.AI_MODEL, "AI_MODEL is required"

        print(f"✅ Configuration loaded successfully")
        print(f"   - AI Provider: {config.AI_PROVIDER}")
        print(f"   - AI Model: {config.AI_MODEL}")
        print(f"   - Telegram Token: {config.TELEGRAM_BOT_TOKEN[:10]}...")
        print(f"   - OpenAI Key: {config.OPENAI_API_KEY[:10]}...")

        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def test_conversation_memory():
    """Test conversation memory functionality."""
    print("\n" + "="*60)
    print("TEST 2: Conversation Memory")
    print("="*60)

    try:
        from src.services.conversation_memory import get_conversation_memory

        memory = get_conversation_memory()
        test_user_id = 123456789

        # Test adding messages
        memory.add_message(test_user_id, "user", "Hello!")
        memory.add_message(test_user_id, "assistant", "Hi there!")
        memory.add_message(test_user_id, "user", "How are you?")

        # Test getting history
        history = memory.get_history(test_user_id)
        assert len(history) == 3, f"Expected 3 messages, got {len(history)}"

        # Test system prompt
        memory.set_system_prompt(test_user_id, "You are a helpful assistant.")
        prompt = memory.get_system_prompt(test_user_id)
        assert prompt == "You are a helpful assistant.", "System prompt not set correctly"

        # Test history with system prompt
        history_with_prompt = memory.get_history(test_user_id)
        assert len(history_with_prompt) == 4, "System prompt should be included"
        assert history_with_prompt[0]["role"] == "system", "First message should be system"

        # Test clearing
        memory.clear_history(test_user_id)
        cleared_history = memory.get_history(test_user_id)
        assert len(cleared_history) == 0, "History should be cleared"

        print(f"✅ Conversation memory working correctly")
        print(f"   - Added and retrieved messages")
        print(f"   - System prompt support working")
        print(f"   - History clearing working")

        return True
    except Exception as e:
        print(f"❌ Conversation memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_ai_service_initialization():
    """Test AI service initialization."""
    print("\n" + "="*60)
    print("TEST 3: AI Service Initialization")
    print("="*60)

    try:
        from src.services.ai_service import get_ai_service

        ai_service = get_ai_service()

        assert ai_service.client is not None, "OpenAI client not initialized"
        assert ai_service.model, "Model not set"
        assert ai_service.max_retries == 3, "Max retries should be 3"

        print(f"✅ AI Service initialized successfully")
        print(f"   - Model: {ai_service.model}")
        print(f"   - Max retries: {ai_service.max_retries}")
        print(f"   - Stream batch interval: {ai_service.stream_batch_interval}s")

        return True
    except Exception as e:
        print(f"❌ AI Service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_imports():
    """Test that all modules can be imported."""
    print("\n" + "="*60)
    print("TEST 4: Module Imports")
    print("="*60)

    modules = [
        "src.config.settings",
        "src.services.conversation_memory",
        "src.services.ai_service",
        "src.handlers.command_handlers",
        "src.handlers.message_handler",
        "src.handlers",
        "src.main",
    ]

    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module}: {e}")
            failed.append(module)

    if failed:
        print(f"\n❌ Failed to import {len(failed)} modules")
        return False

    print(f"\n✅ All modules imported successfully")
    return True


async def test_handler_registration():
    """Test that handlers can be registered."""
    print("\n" + "="*60)
    print("TEST 5: Handler Registration")
    print("="*60)

    try:
        from telegram.ext import ApplicationBuilder
        from src.handlers import register_handlers

        # Create a mock application (we won't run it)
        application = ApplicationBuilder().token("test_token").build()

        # Register handlers
        register_handlers(application)

        print(f"✅ Handlers registered successfully")
        print(f"   (Note: Full handler count requires running bot)")

        return True
    except Exception as e:
        print(f"❌ Handler registration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AI TELEGRAM BOT - FUNCTIONALITY TESTS")
    print("="*60)

    results = []

    # Run tests
    results.append(("Configuration", await test_configuration()))
    results.append(("Imports", await test_imports()))
    results.append(("Conversation Memory", await test_conversation_memory()))
    results.append(("AI Service", await test_ai_service_initialization()))
    results.append(("Handler Registration", await test_handler_registration()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Bot is ready to run.")
        print("\nTo start the bot:")
        print("  python src/main.py")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
