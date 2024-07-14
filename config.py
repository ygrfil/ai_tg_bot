import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "ADMIN_USER_IDS": os.getenv("ADMIN_USER_IDS", "").split(","),
    "ALLOWED_USER_IDS": os.getenv("ALLOWED_USER_IDS", "").split(","),
}

if not ENV["TELEGRAM_BOT_TOKEN"]:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the .env file. Please set it and try again.")

# Add any other configuration variables or functions here
