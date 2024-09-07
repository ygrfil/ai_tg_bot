import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
    "OPENAI_TEMPERATURE": os.getenv("OPENAI_TEMPERATURE"),
    "OPENAI_MAX_TOKENS": os.getenv("OPENAI_MAX_TOKENS"),
    "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL"),
    "ANTHROPIC_TEMPERATURE": os.getenv("ANTHROPIC_TEMPERATURE"),
    "PERPLEXITY_MODEL": os.getenv("PERPLEXITY_MODEL"),
    "GROQ_MODEL": os.getenv("GROQ_MODEL"),
    "GROQ_TEMPERATURE": os.getenv("GROQ_TEMPERATURE"),
    "ADMIN_USER_IDS": os.getenv("ADMIN_USER_IDS").split(","),
    "ALLOWED_USER_IDS": os.getenv("ALLOWED_USER_IDS").split(","),
}

if not ENV["TELEGRAM_BOT_TOKEN"]:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the .env file. Please set it and try again.")

# Add any other configuration variables or functions here
