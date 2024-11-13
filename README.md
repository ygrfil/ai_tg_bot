# 🤖 Telegram AI Assistant Bot

A powerful and flexible Telegram bot that integrates multiple AI providers (OpenAI, Anthropic Claude, Groq, Perplexity) for chat interactions, image analysis, and administrative features.

## ✨ Features

- 🔄 **Multiple AI Providers Support**
  - OpenAI (GPT-4 Vision)
  - Claude 3 Sonnet
  - Groq (Llama 3.2)
  - Perplexity (Llama 3.1)

- 🖼️ **Vision Capabilities**
  - Image analysis and understanding
  - Multi-modal conversations
  - Support for images with or without captions

- 💬 **Chat Features**
  - Stream-based responses for real-time interaction
  - Message history management
  - Automatic cleanup of inactive chats
  - HTML formatting support for rich responses

- 🔐 **Security & Access Control**
  - Admin-only access configuration
  - Whitelist-based user authorization
  - Secure environment variable configuration

- 👑 **Admin Features**
  - User statistics tracking
  - Broadcast messages to all users
  - Administrative command panel

## 🛠️ Technical Stack

- Python 3.13
- aiogram 3.14+ (Telegram Bot Framework)
- SQLite with WAL mode (Chat History & User Settings)
- Docker & Docker Compose
- Multiple AI Provider SDKs:
  - OpenAI
  - Anthropic
  - Groq
  - Perplexity

## 📋 Prerequisites

- Python 3.13+
- Docker (optional)
- API Keys for:
  - Telegram Bot
  - OpenAI
  - Anthropic
  - Groq
  - Perplexity

## 🚀 Installation

1. **Clone the repository**

bash
git clone https://github.com/yourusername/telegram-ai-bot.git
cd telegram-ai-bot

2. **Set up environment variables**
Create a `.env` file with:
```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_id
ALLOWED_USER_IDS=comma,separated,user,ids
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GROQ_API_KEY=your_groq_key
PERPLEXITY_API_KEY=your_perplexity_key
MAX_TOKENS=4096
```

3. **Run with Docker (recommended)**
```bash
docker-compose up --build
```

**OR**

3. **Run locally**
```bash
pip install -r requirements.txt
python main.py
```

## 💡 Usage

1. Start the bot with `/start`
2. Choose an AI provider using the keyboard menu
3. Send text messages or images for AI analysis
4. Use menu buttons for:
   - 🤖 Switching AI models
   - ℹ️ Viewing current configuration
   - 🗑️ Clearing chat history
   - ₿ Checking Bitcoin price
   
## 👑 Admin Commands

- `/admin` - Access admin panel
- `/stats` - View bot statistics
- `/broadcast` - Send message to all users
- `/adminhelp` - Show admin help

## 🔧 Configuration

The bot uses a modular configuration system with:
- Environment-based settings
- Model-specific prompts
- Provider-specific configurations
- Database optimization settings

## 🗃️ Data Management

- Chat history is stored in SQLite with WAL mode
- Automatic cleanup of inactive chats (2 hours)
- Image data temporary storage
- User settings persistence

## 🔒 Security Features

- Rate limiting for API calls
- Secure message sanitization
- Access control via user whitelist
- Docker security best practices
- WAL mode for SQLite database
- Non-root user in Docker

## 🔍 Error Handling

- Comprehensive error catching and logging
- Graceful degradation
- User-friendly error messages
- Automatic reconnection logic

## 🚀 Performance Optimizations

- Stream-based responses
- Rate-limited updates
- Efficient database queries
- Docker volume mounting
- Message buffering
- Typing indicator management

## 📈 Future Improvements

- [ ] Add more AI providers
- [ ] Implement message threading
- [ ] Add user preference persistence
- [ ] Enhance admin analytics
- [ ] Add support for voice messages
- [ ] Implement message scheduling

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [aiogram](https://github.com/aiogram/aiogram) for the excellent Telegram Bot framework
- All AI providers for their APIs
- Contributors and users of the bot
