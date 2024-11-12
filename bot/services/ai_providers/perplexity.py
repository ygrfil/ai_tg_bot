from openai import AsyncOpenAI
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt

class PerplexityProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
        
    async def generate_response(self, prompt: str, model: str = "llama-3.1-sonar-large-128k-online") -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": get_system_prompt(model)},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content