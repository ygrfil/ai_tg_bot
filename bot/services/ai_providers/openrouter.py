from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
import asyncio
from openai import AsyncOpenAI
from .base import BaseAIProvider
from ...config import Config
import logging

class OpenRouterProvider(BaseAIProvider):
    """OpenRouter provider using OpenAI SDK for optimal performance."""
    
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(api_key, config)
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/ygrfil/ai_tg_bot",
                "X-Title": "AI Telegram Bot"
            },
            timeout=30.0  # 30 second timeout
        )

    async def chat_completion_stream(
        self,
        message: str,
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using OpenAI SDK for optimal performance."""
        
        try:
            messages = []
            
            # Add system message
            system_prompt = self._get_system_prompt(model_config.get('name', ''))
            messages.append({"role": "system", "content": system_prompt})
            
            # Add history (limit to recent messages for speed)
            if history:
                messages.extend(self._format_history(history[-6:], model_config))  # Only last 6 messages
            
            # Add current message with image if provided
            if image and self._supports_vision(model_config):
                base64_image = base64.b64encode(image).decode('utf-8')
                messages.append(self._format_image_message(message, base64_image))
            else:
                messages.append({"role": "user", "content": message})

            # Create streaming completion with optimized parameters
            stream = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                stream=True,
                max_tokens=2048,  # Limit tokens for faster responses
                temperature=0.7,   # Slightly lower temperature for speed
            )
            
            # Stream the response
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        yield delta.content
                        
        except Exception as e:
            logging.error(f"Error in OpenRouter streaming: {e}")
            yield f"❌ Error: {str(e)}. Please try again later."