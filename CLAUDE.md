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
pip install --upgrade aiogram openai aiohttp aiosqlite aiofiles pydantic
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
- **`bot/services/ai_providers/`** - AI provider abstractions and implementations with caching
- **`bot/services/async_file_manager.py`** - Non-blocking file I/O operations
- **`bot/schemas/`** - Structured output schemas for reliable AI responses
- **`bot/config/`** - Configuration management and AI model prompts
- **`bot/services/storage.py`** - SQLite database operations with connection pooling

### AI Provider System
The bot uses a multi-provider architecture supporting:
- **OpenRouter** - Access to GPT-4o, Claude 3.5 Sonnet, Llama models
- **Fal AI** - Image generation capabilities
- **Base Provider Pattern** - Abstract class in `bot/services/ai_providers/base.py`

Each provider implements:
- `chat_completion_stream()` - Text generation with streaming support
- `chat_completion_structured()` - Structured outputs with JSON schema compliance
- `send_message_with_image()` - Vision capabilities for image analysis
- Provider-specific model configurations in `providers.py`
- **Provider caching** - Instances cached to avoid recreation overhead

### Database Design
- **SQLite with WAL mode** - Optimized for concurrent access
- **Connection pooling** - Advanced pool with 2-10 connections, automatic cleanup
- **Async file operations** - Non-blocking image storage using aiofiles
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
- **Structured outputs** - JSON schema compliance for reliable parsing
- **Smart response formatting** - Different formatting for code, math, analysis, help responses
- **HTML formatting** - Rich text support
- **Rate limiting** - Configurable delays between message updates
- **Vision support** - Image analysis across multiple AI providers
- **Performance optimized** - 70-250ms faster response times

### Security Implementation
- **Whitelist authorization** - Only `ALLOWED_USER_IDS` can interact
- **Admin-only features** - Separate admin command handlers
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

## Performance Optimizations (2025)

The bot has been significantly optimized with three major improvements:

### 1. AI Provider Instance Caching
- **Location**: `bot/services/ai_providers/provider_cache.py`
- **Benefit**: 50-150ms improvement per message
- **Implementation**: Providers cached globally, eliminating recreation overhead
- **Features**: Performance statistics, automatic cleanup, async interface

### 2. Async File I/O Operations  
- **Location**: `bot/services/async_file_manager.py`
- **Benefit**: 20-100ms improvement + better concurrency
- **Implementation**: Non-blocking image saves using aiofiles and background threads
- **Features**: Background task execution, performance monitoring, thread pools

### 3. Structured Outputs (OpenAI 2025 API)
- **Location**: `bot/schemas/response_schemas.py`
- **Benefit**: Guaranteed JSON schema compliance, improved reliability
- **Implementation**: 8 response types with automatic detection and formatting
- **Features**: Smart type detection, rich formatting, graceful fallback

### Response Types and Formatting
The bot automatically detects query types and uses structured outputs for:

- **Math**: Step-by-step solutions with final answers and units
- **Code**: Formatted code blocks with explanations and language detection
- **Analysis**: Organized findings, methodology, and key insights
- **Help**: Structured instructions with related commands
- **Image Analysis**: Object detection, scene description, text extraction
- **Error Handling**: Structured error responses with suggestions

### Commands
- **`/structured <question>`** - Force structured output for testing
- **Auto-detection** - Automatically uses structured outputs for supported query types
- **Fallback mode** - Falls back to streaming for general conversation

### API Versions
- **OpenAI SDK**: `>=1.62.0` (supports structured outputs)
- **Pydantic**: `>=2.9.0` (schema validation)
- **aiofiles**: `>=23.1.0` (async file operations)