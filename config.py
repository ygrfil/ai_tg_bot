import os
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_model_config(file_path: str) -> Dict[str, str]:
    config = {}
    with open(file_path, 'r') as file:
        for line in file:
            key, value = line.strip().split('=')
            config[key] = value
    return config

MODEL_CONFIG = load_model_config('models_names.txt')

# Add base URLs for models using OpenAI-compatible API
MODEL_CONFIG.update({
    "perplexity_base_url": "https://api.perplexity.ai",
    "groq_base_url": "https://api.groq.com/openai/v1",
    "hyperbolic_base_url": "https://api.hyperbolic.ai"
})

ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
    "OPENAI_TEMPERATURE": os.getenv("OPENAI_TEMPERATURE"),
    "OPENAI_MAX_TOKENS": os.getenv("OPENAI_MAX_TOKENS"),
    "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL"),
    "ANTHROPIC_TEMPERATURE": os.getenv("ANTHROPIC_TEMPERATURE"),
    "PERPLEXITY_API_KEY": os.getenv("PERPLEXITY_API_KEY"),
    "PERPLEXITY_MODEL": os.getenv("PERPLEXITY_MODEL"),
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    "GROQ_MODEL": os.getenv("GROQ_MODEL"),
    "GROQ_TEMPERATURE": os.getenv("GROQ_TEMPERATURE"),
    "HYPERBOLIC_API_KEY": os.getenv("HYPERBOLIC_API_KEY"),
    "ADMIN_USER_IDS": os.getenv("ADMIN_USER_IDS", "").split(","),
    "ALLOWED_USER_IDS": os.getenv("ALLOWED_USER_IDS", "").split(","),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
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

# Add any other configuration variables or functions here
