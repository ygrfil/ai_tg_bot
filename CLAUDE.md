# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Bot
```bash
# Local development
python main.py

# Docker development
docker-compose up --build

# Production deployment
docker-compose up -d
```

### Dependencies
```bash
# Install dependencies
pip install -r requirements.txt

# Update dependencies (check requirements.txt for version constraints)
pip install --upgrade aiogram openai anthropic groq aiohttp aiosqlite
```

### Environment Setup
Required environment variables in `.env`:
- `BOT_TOKEN` - Telegram Bot API token
- `ADMIN_ID` - Telegram user ID for admin access
- `ALLOWED_USER_IDS` - Comma-separated list of authorized user IDs
- `OPENROUTER_API_KEY` - OpenRouter API key for multiple AI models
- `FAL_API_KEY` - Fal AI API key for image generation
- `MAX_TOKENS` - Response token limit (default: 1024)

## Architecture Overview

### Core Components
- **`main.py`** - Entry point that initializes bot, middleware, and handlers
- **`bot/handlers/`** - Request handlers for user interactions and admin functions
- **`bot/services/ai_providers/`** - AI provider abstractions and implementations
- **`bot/config/`** - Configuration management and AI model prompts
- **`bot/storage.py`** - SQLite database operations with connection pooling

### AI Provider System
The bot uses a multi-provider architecture supporting:
- **OpenRouter** - Access to GPT-4o, Claude 3.5 Sonnet, Llama models
- **Fal AI** - Image generation capabilities
- **Base Provider Pattern** - Abstract class in `bot/services/ai_providers/base.py`

Each provider implements:
- `send_message()` - Text generation with streaming support
- `send_message_with_image()` - Vision capabilities for image analysis
- Provider-specific model configurations in `providers.py`

### Database Design
- **SQLite with WAL mode** - Optimized for concurrent access
- **Connection pooling** - Single connection per database file
- **Automatic cleanup** - Removes inactive chats after 2 hours
- **Chat history persistence** - Maintains conversation context

### State Management
Uses aiogram's FSM (Finite State Machine) with states defined in `bot/states.py`:
- `ChatState.chatting` - Active conversation mode
- `ChatState.choosing_provider` - AI provider selection
- `AdminState.*` - Administrative operations
- `ImageGenState.*` - Image generation workflow

### Message Handling
- **Streaming responses** - Real-time message updates using `edit_message_text()`
- **HTML formatting** - Rich text support with sanitization
- **Rate limiting** - Configurable delays between message updates
- **Vision support** - Image analysis across multiple AI providers

### Security Implementation
- **Whitelist authorization** - Only `ALLOWED_USER_IDS` can interact
- **Admin-only features** - Separate admin command handlers
- **Message sanitization** - HTML tag cleaning for safe display
- **Docker security** - Non-root user execution (UID 1000)

## Key Development Patterns

### Adding New AI Providers
1. Create new provider class inheriting from `BaseAIProvider`
2. Implement required methods: `send_message()` and `send_message_with_image()`
3. Add provider configuration to `bot/services/ai_providers/providers.py`
4. Update provider selection keyboard in `bot/keyboards/`

### Database Operations
All database operations use the connection pool in `bot/storage.py`:
- Use `get_connection()` context manager for transactions
- Follow existing patterns for chat history and user settings
- WAL mode is enabled for better concurrent performance

### Error Handling
- Catch provider-specific exceptions and convert to user-friendly messages
- Use logging for debugging while maintaining user experience
- Implement graceful degradation when providers are unavailable

### Message Processing
- Always check message content and user authorization first
- Use FSM states to control conversation flow
- Implement streaming for long responses to improve user experience
- Handle both text and image inputs consistently across providers