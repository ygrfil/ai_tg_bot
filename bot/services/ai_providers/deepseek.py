from .openai import OpenAIProvider
from bot.config import Config
from openai import AsyncOpenAI

class DeepSeekProvider(OpenAIProvider):
    def __init__(self, api_key: str, config: Config):
        super().__init__(api_key, config)
        self.model_name = "DeepSeek-reasoner"
        self.base_url = "https://api.deepseek.com/v1"
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=30.0
        )
        
    def _get_system_prompt(self, model_name: str) -> str:
        """Custom system prompt for DeepSeek"""
        return "You are a helpful AI assistant. Respond concisely and accurately."