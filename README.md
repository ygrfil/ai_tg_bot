# AI Telegram Bot

A Telegram bot that lets you chat with various AI models and analyze images.

## Features

- Chat with multiple AI models (GPT-4, Claude, etc.)
- Send images for AI analysis
- Customize AI behavior with system prompts
- Track Bitcoin prices
- Admin controls and usage statistics

## Quick Start

1. Clone and install:
```bash
git clone https://github.com/yourusername/tg_ai_bot.git
cd tg_ai_bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Create `.env` file with your API keys:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
ADMIN_USER_IDS=your_admin_ids
ALLOWED_USER_IDS=allowed_user_ids
```

3. Start the bot:
```bash
python main.py
```

## Commands

User Commands:
- `/start` - Get started
- `/model` - Select AI model
- `/sm` - Choose system prompt
- `/reset` - Reset conversation
- `/status` - View your settings
- `/btc` - Get Bitcoin price

Admin Commands:
- `/startadmin` - Admin menu
- `/broadcast` - Message all users
- `/usage` - View statistics
- `/list_users` - Show users
- `/add_user` - Add user
- `/remove_user` - Remove user
- `/reload` - Reload config

## Docker Support

Build and run with Docker:
```bash
docker-compose up --build
```

Stop:
```bash
docker-compose down
```

## License

MIT License
