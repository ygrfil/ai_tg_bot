import os
import logging
from typing import Dict
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

def load_model_config(file_path: str) -> Dict[str, str]:
    config = {}
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
            except ValueError:
                logger.warning(f"Skipping invalid line in {file_path}: {line}")
    return config

MODEL_CONFIG = load_model_config('models_names.txt')

for model in ['openai', 'anthropic', 'perplexity', 'groq', 'gemini']:
    MODEL_CONFIG.setdefault(f'{model}_model', os.getenv(f'{model.upper()}_MODEL', ''))
    MODEL_CONFIG.setdefault(f'{model}_temperature', os.getenv(f'{model.upper()}_TEMPERATURE', '0.7'))
    MODEL_CONFIG.setdefault(f'{model}_max_tokens', os.getenv(f'{model.upper()}_MAX_TOKENS', '1024'))

ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "PERPLEXITY_API_KEY": os.getenv("PERPLEXITY_API_KEY"),
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "ADMIN_USER_IDS": os.getenv("ADMIN_USER_IDS", "").split(","),
    "ALLOWED_USER_IDS": os.getenv("ALLOWED_USER_IDS", "").split(","),
}

print("Environment variables loaded:")
for key, value in ENV.items():
    if key in ["ADMIN_USER_IDS", "ALLOWED_USER_IDS"]:
        print(f"{key}: [REDACTED]")
    elif "API_KEY" in key or key == "TELEGRAM_BOT_TOKEN":
        print(f"{key}: {'[SET]' if value else '[NOT SET]'}")
    else:
        print(f"{key}: {value}")

if not ENV["TELEGRAM_BOT_TOKEN"]:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the .env file. Please set it and try again.")
