# AI Chatbot for Telegram

This Telegram bot provides an interface to interact with various AI models, offering a range of features for both users and administrators.

## Features

### General Features

- **Multiple AI Models**: Choose between OpenAI, Anthropic, Perplexity, Groq, and Hyperbolic models.
- **Customizable System Prompts**: Select or create different AI behaviors and contexts.
- **Image Processing**: Send images for analysis (OpenAI and Anthropic models only).
- **Conversation Management**: Maintains history with automatic reset after 2 hours of inactivity.
- **Status Check**: View current model, system prompt, and usage statistics.

### User Commands

- `/start`: Introduction and available commands.
- `/model`: Select AI model.
- `/sm`: Choose system prompt.
- `/reset`: Reset conversation history.
- `/create_prompt`: Create a new system prompt.
- `/status`: View current settings and usage.
- `/btc`: Get the current Bitcoin price.

### Admin Commands

- `/startadmin`: View admin commands.
- `/broadcast`: Send a message to all users.
- `/usage`: View usage statistics.
- `/list_users`: List all allowed users.
- `/add_user`: Add a new allowed user.
- `/remove_user`: Remove an allowed user.
- `/remove_prompt`: Remove a system prompt.
- `/reload`: Reload the model configuration.

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
