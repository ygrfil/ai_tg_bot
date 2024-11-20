from typing import Dict, Any, List, Optional, AsyncGenerator
from openai import AsyncOpenAI
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt
from ...config.settings import Config

class PerplexityProvider(BaseAIProvider):
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )

    async def chat_completion_stream(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        formatted_messages = []
        
        system_prompt = get_system_prompt(model_config['name'])
        if system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": system_prompt
            })
            
        if history:
            for msg in history:
                formatted_messages.append({
                    "role": "user" if not msg.get("is_bot") else "assistant",
                    "content": msg["content"]
                })

        formatted_messages.append({
            "role": "user",
            "content": message
        })

        try:
            stream = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=formatted_messages,
                temperature=0.7,
                max_tokens=self._get_max_tokens(model_config),
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise Exception(f"Perplexity error: {str(e)}")