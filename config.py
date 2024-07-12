import os

ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "ALLOWED_USER_IDS": os.getenv("ALLOWED_USER_IDS", "").split(","),
    "ADMIN_USER_IDS": os.getenv("ADMIN_USER_IDS", "").split(","),
}

# Add any other configuration variables or functions here
