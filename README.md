# AI Telegram Assistant

A modern Python-based Telegram bot powered by AI, built with clean architecture and best practices.

## Features

- Telegram bot integration
- AI-powered responses
- Database persistence
- Modular architecture
- Docker support
- Type hints and validation

## Prerequisites

- Python 3.13+
- Docker & Docker Compose (optional)
- Telegram Bot Token
- OpenAI/Anthropic API Key

## Installation

### Local Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-telegram-assistant
```

2. Create virtual environment:
```bash
python -m venv venv
```

3. Activate virtual environment:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Copy environment variables:
```bash
cp .env.example .env
```

6. Configure `.env` with your credentials

7. Run the bot:
```bash
python -m src.main
```

### Docker Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-telegram-assistant
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Configure `.env` with your credentials

4. Start services:
```bash
docker-compose up --build
```

## Project Structure

```
src/
├── handlers/          # Telegram bot handlers
├── services/          # Business logic services
├── database/          # Database models and migrations
├── middlewares/       # Bot middlewares
├── config/           # Configuration management
├── utils/            # Utility functions
└── logs/             # Log files

tests/                # Test files
docs/                 # Documentation
```

## Development

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint
flake8 src/ tests/

# Type check
mypy src/
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src
```

## Environment Variables

See `.env.example` for required environment variables.

## License

MIT
