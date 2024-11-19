from groq import AsyncGroq
from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
from .base import BaseAIProvider
from ...config.settings import Config
from ...config.prompts import get_system_prompt
import logging
from openai import AsyncOpenAI

class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str, config: Config = None):
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
            
            # Don't add system prompt for vision models when image is present
            if not image and not any(msg.get("image") for msg in (history or [])):
                system_prompt = get_system_prompt(model_config['name'])
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})

            # Process history - only include text messages if current request has image
            if history:
                for msg in history:
                    # Skip messages with images if we have a new image
                    if image and msg.get("image"):
                        continue
                        
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

            # Add current message with image if present
            if image and model_config.get('vision'):
                # Check image size (4MB limit for base64)
                if len(image) > 4 * 1024 * 1024:
                    raise Exception("Image size exceeds 4MB limit")
                    
                base64_image = base64.b64encode(image).decode('utf-8')
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": message or "What's in this image?"},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }}
                    ]
                })
            else:
                messages.append({
                    "role": "user",
                    "content": message
                })

            # Create completion with specific parameters for Groq
            response = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                temperature=0.7,
                max_tokens=self._get_max_tokens(model_config),
                stream=True
            )
            
            async for chunk in response:
                if hasattr(chunk.choices[0].delta, 'content'):
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                    
            logging.info("GroqProvider: Completed chat_completion_stream")
        except Exception as e:
            logging.error(f"GroqProvider Error: {e}")
            raise
