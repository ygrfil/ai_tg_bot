from groq import AsyncGroq
from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
from .base import BaseAIProvider
from ...config.settings import Config
from ...config.prompts import get_system_prompt
import logging

class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str, config: Config):
        super().__init__(config)
        self.client = AsyncGroq(api_key=api_key)
        
    async def chat_completion_stream(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        logging.info("GroqProvider: Starting chat_completion_stream")
        try:
            messages = []
            
            # Handle image input
            if image is not None and model_config.get('vision', False):
                base64_image = base64.b64encode(image).decode('utf-8')
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": message or "What's in this image?"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                })
            else:
                # Handle text-only input
                if history:
                    for msg in history:
                        if msg.get("is_bot"):
                            messages.append({
                                "role": "assistant",
                                "content": msg["content"]
                            })
                        else:
                            messages.append({
                                "role": "user",
                                "content": msg["content"]
                            })
                
                messages.append({
                    "role": "user",
                    "content": message
                })

            # Create chat completion
            stream = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                stream=True,
                max_tokens=self.config.max_tokens,
                temperature=0.7
            )

            async for chunk in stream:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                        if choice.delta.content:
                            yield choice.delta.content

        except Exception as e:
            logging.error(f"GroqProvider error: {str(e)}")
            raise Exception(f"Groq error: {str(e)}")
