# Telegram AI Bot

This is a Telegram bot that uses various AI models to respond to user messages and perform different tasks.

## Features

- Supports multiple AI models (OpenAI, Anthropic, Perplexity, Groq)
- Customizable system prompts
- Image analysis capabilities
- Conversation summarization
- Usage tracking and reporting

## Installation

### Option 1: Standard Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/tg_ai_bot.git
   cd tg_ai_bot
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory and add your API keys:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ADMIN_USER_IDS=comma_separated_admin_user_ids
   ALLOWED_USER_IDS=comma_separated_allowed_user_ids
   ```

### Option 2: Docker Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/tg_ai_bot.git
   cd tg_ai_bot
   ```

2. Create a `.env` file in the root directory with your API keys (as shown in Option 1, step 3).

3. Build and run the Docker container:
   ```
   docker-compose up --build
   ```

## Usage

### For Standard Installation:

1. Start the bot:
   ```
   python main.py
   ```

### For Docker Installation:

The bot will start automatically when you run `docker-compose up`. To stop the bot, use:
```
docker-compose down
```

2. In Telegram, start a conversation with your bot and use the following commands:

   - `/start`: Introduces the bot and explains available AI models
   - `/model`: Select the AI model (OpenAI, Anthropic, Perplexity, or Groq)
   - `/sm`: Select a system message to set the AI behavior and context
   - `/reset`: Reset the conversation history
   - `/summarize`: Summarize the current conversation
   - `/create_prompt`: Create a new system prompt

   Admin commands:
   - `/startadmin`: Shows all admin commands
   - `/broadcast`: Send a message to all users
   - `/usage`: View usage statistics
   - `/list_users`: List all allowed users
   - `/add_user`: Add a new allowed user
   - `/remove_user`: Remove an allowed user

3. Send text messages or images to interact with the AI model.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.
