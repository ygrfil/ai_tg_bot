import os
from dotenv import load_dotenv

load_dotenv()

ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "ALLOWED_USER_IDS": set(os.getenv("ALLOWED_USER_IDS", "").split(",")),
    "ADMIN_USER_IDS": set(os.getenv("ADMIN_USER_IDS", "").split(",")),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "PPLX_API_KEY": os.getenv("PPLX_API_KEY"),
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
}

AVAILABLE_MODELS = ["openai", "anthropic", "perplexity", "groq"]
