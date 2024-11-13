from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any
from .base import BaseAIProvider

class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )

    async def chat_completion(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        messages = []
        if history:
            messages.extend(self._format_history(history))
        
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model="mixtral-8x7b-32768",  # Groq's specific model
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Groq error: {str(e)}")
