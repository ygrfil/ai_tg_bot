# Advanced AI Telegram Bot

A powerful and versatile Telegram bot that provides seamless access to multiple AI language models, offering advanced features for both users and administrators. The bot supports natural language processing, image analysis, and various utility functions.

## Key Features

### AI Model Integration
- **Multiple AI Providers**:
  - OpenAI (GPT-4 and variants)
  - Anthropic (Claude and variants)
  - Perplexity AI
  - Groq
  - Gemini
- **Model Selection**: Switch between models using `/model` command
- **Customizable Parameters**: Temperature and token limits configurable per model

### Image Processing
- **Image Analysis**: Send images for AI analysis (supported by OpenAI and Anthropic)
- **Multi-Modal Understanding**: Process images with text captions
- **Format Handling**: Supports various image formats and sizes

### Conversation Management
- **History Tracking**: Maintains conversation context
- **Auto-Reset**: Conversations automatically reset after 2 hours of inactivity
- **Manual Reset**: Use `/reset` command to start fresh
- **Context Length Management**: Automatic handling of context limitations

### System Prompts
- **Customizable Behavior**: Multiple pre-defined system prompts
- **Custom Prompts**: Create and manage custom prompts
- **Quick Switching**: Easy switching between different AI behaviors
- **Prompt Management**: Add, remove, and modify system prompts

### User Management
- **Access Control**: Whitelist-based user authorization
- **Admin Controls**: Comprehensive admin interface
- **Usage Tracking**: Detailed usage statistics per user
- **Rate Limiting**: Built-in protection against overuse

### Utility Features
- **Cryptocurrency**: Real-time Bitcoin price tracking (`/btc`)
- **Broadcasting**: Send announcements to all users
- **Status Monitoring**: Check bot status and configuration
- **Error Handling**: Robust error management and user feedback

### Commands

#### User Commands
- `/start` - Introduction and basic instructions
- `/model` - Select AI model
- `/sm` - Choose system prompt
- `/reset` - Reset conversation
- `/create_prompt` - Create custom system prompt
- `/status` - View current settings and usage
- `/btc` - Get Bitcoin price

#### Admin Commands
- `/startadmin` - Access admin interface
- `/broadcast` - Send message to all users
- `/usage` - View detailed usage statistics
- `/list_users` - Show all authorized users
- `/add_user` - Add new authorized user
- `/remove_user` - Remove user access
- `/remove_prompt` - Delete system prompt
- `/reload` - Reload configuration

### Security Features
- **API Key Management**: Secure handling of API keys
- **User Authentication**: Multi-level access control
- **Error Protection**: Graceful handling of API limits and errors
- **Data Privacy**: Minimal data storage and secure handling

### Performance
- **Asynchronous Processing**: Efficient handling of requests
- **Resource Management**: Optimized memory and API usage
- **Reliability**: Automatic reconnection and error recovery
- **Scalability**: Designed for growing user base

## Installation

### Option 1: Standard Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/tg_ai_bot.git
   cd tg_ai_bot
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the configuration (see Configuration section below).

5. Start the bot:
   ```bash
   python main.py
   ```

### Option 2: Docker Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/tg_ai_bot.git
   cd tg_ai_bot
   ```

2. Set up the configuration (see Configuration section below).

3. Build and run the Docker container:
   ```bash
   docker-compose up --build
   ```

4. To stop the bot, use:
   ```bash
   docker-compose down
   ```

## Configuration

1. Create a `.env` file in the root directory of the project.

2. Add the following environment variables to the `.env` file:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ADMIN_USER_IDS=comma_separated_admin_user_ids
   ALLOWED_USER_IDS=comma_separated_allowed_user_ids
   ```

   Replace the placeholders with your actual API keys and user IDs.

3. (Optional) Additional configuration options can be set in `config.py`.

## Usage

1. Start a conversation with your bot on Telegram.

2. Use the commands listed in the Features section to interact with the bot.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them with clear, descriptive messages.
4. Push your changes to your fork.
5. Submit a pull request to the main repository.

Please ensure your code adheres to the existing style and includes appropriate tests and documentation.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
