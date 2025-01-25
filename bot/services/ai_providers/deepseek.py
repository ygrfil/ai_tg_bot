from .openai import OpenAIProvider
from bot.config import Config
from openai import AsyncOpenAI

from bot.config.prompts import get_system_prompt

class DeepSeekProvider(OpenAIProvider):
    def __init__(self, api_key: str, config: Config):
        super().__init__(api_key, config)
        self.model_name = "deepseek-v3.0-chat"
        self.base_url = "https://api.deepseek.com/v1"
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=30.0
        )

    def _get_system_prompt(self, model_name: str) -> str:
        """Get configured system prompt for DeepSeek"""
        return get_system_prompt(self.model_name)