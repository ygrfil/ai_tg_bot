# AI Chatbot for Telegram

This Telegram bot provides an interface to interact with various AI models, offering a range of features for both users and administrators.

## Key Changes

### Refactor Repeated Authorization Checks
- Introduced an `admin_only` decorator in `src/utils/decorators.py` to centralize authorization logic for admin commands.

### Simplify Model Display Names
- Simplified the `model_display_names` dictionary in `src/handlers/handlers.py` using a dictionary comprehension with the `MODEL_CONFIG` dictionary.

### Use Constants for Default Values
- Introduced `DEFAULT_MODEL` and `DEFAULT_PROMPT` constants in `src/database/database.py` to avoid magic strings for default values.

## Features

### For All Users

1. **Multiple AI Models**: Choose between OpenAI, Anthropic, Perplexity, and Groq models.
2. **Customizable System Prompts**: Select or create different AI behaviors and contexts.
3. **Image Processing**: Send images for analysis (OpenAI and Anthropic models only).
4. **Conversation Management**: Maintains history with automatic reset after 2 hours of inactivity.
5. **Status Check**: View current model, system prompt, and usage statistics.

### For Administrators

1. **Broadcast Messages**: Send messages to all users.
2. **Usage Statistics**: View detailed usage stats for all users.
3. **User Management**: List, add, or remove allowed users.
4. **System Prompt Management**: Remove custom system prompts.

## Installation

### Option 1: Standard Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/tg_ai_bot.git
   cd tg_ai_bot
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up the configuration (see Configuration section below).

5. Start the bot:
   ```
   python main.py
   ```

### Option 2: Docker Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/tg_ai_bot.git
   cd tg_ai_bot
   ```

2. Set up the configuration (see Configuration section below).

3. Build and run the Docker container:
   ```
   docker-compose up --build
   ```

4. To stop the bot, use:
   ```
   docker-compose down
   ```

## Configuration

1. Create a `.env` file in the root directory of the project.

2. Add the following environment variables to the `.env` file:
   ```
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

2. Use the following commands:

### User Commands
- `/start`: Introduction and available commands
- `/model`: Select AI model
- `/sm`: Choose system prompt
- `/reset`: Reset conversation history
- `/create_prompt`: Create a new system prompt
- `/status`: View current settings and usage

### Admin Commands
- `/startadmin`: View admin commands
- `/broadcast`: Send a message to all users
- `/usage`: View usage statistics
- `/list_users`: List all allowed users
- `/add_user`: Add a new allowed user
- `/remove_user`: Remove an allowed user
- `/remove_prompt`: Remove a system prompt

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
