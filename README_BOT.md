# AI Telegram Assistant Bot

A robust Telegram chatbot powered by OpenAI's GPT models with conversation memory, streaming responses, and comprehensive error handling.

## Features

- 🤖 **OpenAI Integration**: Powered by GPT-4o-mini (configurable)
- 💬 **Conversation Memory**: Maintains context across messages (last 10 messages per user)
- ⚡ **Streaming Responses**: Real-time response updates with batched message edits
- 🔄 **Retry Logic**: Exponential backoff for API failures
- 🎯 **System Prompts**: Configurable bot personality
- 📊 **Token Tracking**: Logs token usage for every response
- 🛡️ **Error Recovery**: Graceful error handling without crashes
- 🔒 **Secure**: Environment variables for all API keys

## Tech Stack

- **Language**: Python 3.9+
- **Telegram Bot**: python-telegram-bot v21.10
- **AI/LLM**: OpenAI API (gpt-4o-mini)
- **Configuration**: pydantic-settings + python-dotenv
- **Retry Logic**: tenacity
- **Async**: asyncio

## Project Structure

```
src/
├── config/
│   └── settings.py          # Configuration management with validation
├── services/
│   ├── ai_service.py        # OpenAI API integration with streaming
│   └── conversation_memory.py  # Per-user conversation history
├── handlers/
│   ├── __init__.py          # Handler registration
│   ├── command_handlers.py  # /start, /help, /about, /ping, /settings
│   └── message_handler.py   # Text message handling with AI responses
├── middlewares/             # Middleware system
├── database/               # Database layer (optional)
├── utils/
│   └── logger.py           # Logging configuration
└── main.py                 # Application entry point
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd AI Telegram Assistant
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# Copy from example
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# OpenAI API Key (from platform.openai.com)
OPENAI_API_KEY=your_openai_api_key_here

# AI Configuration
AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini

# Optional: Database (for future features)
DATABASE_URL=sqlite+aiosqlite:///telegram_bot.db

# Optional: Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 5. Get Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the token (format: `123456789:ABCdef...`)

### 6. Get OpenAI API Key

1. Visit [platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Go to API Keys section
4. Create a new API key
5. Copy the key (format: `sk-...`)

### 7. Run the Bot

```bash
python src/main.py
```

You should see:
```
INFO - Initializing bot...
INFO - Database initialized successfully!
INFO - Bot initialized successfully!
INFO - Bot username: @YourBotName
INFO - Starting polling...
INFO - Bot started successfully!
```

## Usage

### Basic Commands

- `/start` - Start the bot and get welcome message
- `/help` - Show available commands
- `/about` - Bot information
- `/ping` - Check bot latency
- `/settings` - Configure preferences (coming soon)

### Chat with AI

Simply send any text message to the bot, and it will:
1. Add your message to conversation history
2. Send a "Thinking..." status message
3. Stream the AI response with real-time updates
4. Log token usage to console

### Conversation Memory

The bot maintains conversation context:
- Stores last 10 messages per user
- Includes system prompt for personality
- Automatically manages token limits
- Clears when bot restarts (in-memory only)

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot token from @BotFather |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `AI_PROVIDER` | No | `openai` | AI provider (`openai` or `anthropic`) |
| `AI_MODEL` | No | `gpt-4o-mini` | OpenAI model to use |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///telegram_bot.db` | Database connection |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | No | `json` | Log format (`json` or `text`) |

### System Prompt

The default system prompt is defined in `src/handlers/message_handler.py`:

```python
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, friendly, and knowledgeable AI assistant. "
    "You provide clear, accurate, and concise responses. "
    "You maintain context from the conversation to provide relevant answers. "
    "If you don't know something, you say so honestly."
)
```

You can customize this by modifying the `DEFAULT_SYSTEM_PROMPT` constant.

## Architecture

### Core Components

#### 1. Configuration Management (`src/config/settings.py`)
- Pydantic-based configuration with validation
- Environment variable loading from `.env`
- Type-safe access to configuration values
- Validation for required fields

#### 2. Conversation Memory (`src/services/conversation_memory.py`)
- Thread-safe in-memory storage per user
- Configurable history limit (default: 10 messages)
- System prompt support per user
- OpenAI-compatible message format

#### 3. AI Service (`src/services/ai_service.py`)
- OpenAI API integration with async client
- Streaming response generation
- Exponential backoff retry logic (3 attempts)
- Token usage tracking and logging
- Error handling with custom exceptions

#### 4. Message Handler (`src/handlers/message_handler.py`)
- Handles incoming text messages
- Implements streaming with batched updates (1.5s intervals)
- Rate limit protection (ignores 429 errors during streaming)
- User-friendly error messages

### Data Flow

```
User Message → Telegram → Message Handler
                              ↓
                    Add to Conversation Memory
                              ↓
                    Send "Thinking..." Status
                              ↓
                    OpenAI API (Streaming)
                              ↓
                    Update Message (Batched)
                              ↓
                    Log Token Usage
                              ↓
                    Complete Response
```

## Error Handling

### Retry Logic

The bot implements exponential backoff for OpenAI API calls:
- **Max Retries**: 3 attempts
- **Wait Strategy**: Exponential (2s, 4s, 8s)
- **Retryable Errors**: Network issues, rate limits, API errors

### Error Recovery

If an unrecoverable error occurs:
1. Logs the error with full traceback
2. Sends user-friendly error message
3. Bot continues running (no crash)

### Rate Limiting

To avoid Telegram's `429 Too Many Requests`:
- Batches message updates every 1.5 seconds
- Ignores 429 errors during streaming
- Falls back to new message if edit fails

## Token Usage Tracking

Token usage is logged after every complete response:

```
INFO - Token usage for user 123456789: Token Usage - Prompt: 45, Completion: 120, Total: 165
```

This helps monitor API costs and optimize prompts.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_database.py
```

### Code Quality

```bash
# Format code
black src/

# Lint
flake8 src/

# Type check
mypy src/
```

### Adding New Features

1. **New Commands**: Add handler in `src/handlers/command_handlers.py`
2. **New Message Types**: Add handler in `src/handlers/message_handler.py`
3. **New AI Providers**: Extend `src/services/ai_service.py`
4. **Database Features**: Use existing `src/database/` layer

## Troubleshooting

### Bot Not Starting

**Issue**: `TELEGRAM_BOT_TOKEN is not set!`

**Solution**: Ensure `.env` file exists and contains valid `TELEGRAM_BOT_TOKEN`

### OpenAI API Errors

**Issue**: `OpenAI API call failed: ...`

**Solution**:
- Verify `OPENAI_API_KEY` in `.env`
- Check API key has credits
- Ensure API key has correct permissions

### Rate Limit Errors

**Issue**: Frequent `429 Too Many Requests` from Telegram

**Solution**:
- Increase `update_interval` in `message_handler.py` (default: 1.5s)
- Reduce message update frequency
- Bot already handles 429 gracefully during streaming

### Import Errors

**Issue**: `ModuleNotFoundError`

**Solution**:
```bash
# Ensure virtual environment is activated
pip install -r requirements.txt
```

## Production Deployment

### Environment Variables

```env
APP_ENV=production
APP_DEBUG=false
TELEGRAM_BOT_TOKEN=your_production_token
OPENAI_API_KEY=your_production_key
SECRET_KEY=your_secure_secret_key_here_minimum_32_chars
DATABASE_URL=postgresql://user:pass@host:5432/dbname
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Security Considerations

1. **Never commit `.env`** - Already in `.gitignore`
2. **Use strong SECRET_KEY** - Minimum 32 characters
3. **Rotate API keys regularly** - Especially if compromised
4. **Monitor token usage** - Set up alerts for unusual usage
5. **Use production database** - Not SQLite for production

### Deployment Options

- **Docker**: Use provided `Dockerfile` and `docker-compose.yml`
- **VPS**: Run with `systemd` service
- **Serverless**: Deploy to AWS Lambda, GCP Cloud Functions
- **PaaS**: Deploy to Heroku, Railway, Render

## License

MIT License - feel free to use this project for your own bots!

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review code comments

---

Built with ❤️ using python-telegram-bot and OpenAI API
