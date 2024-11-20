from openai import AsyncOpenAI
import base64
from typing import Optional, List, Dict, Any, AsyncGenerator
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt
from ...config.settings import Config
import logging

class OpenAIProvider(BaseAIProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None, config: Config = None):
        super().__init__(config)
        self.api_key = api_key
        self.base_url = base_url

    async def chat_completion_stream(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        logging.info("OpenAIProvider: Starting chat_completion_stream")
        try:
            async with AsyncOpenAI(api_key=self.api_key, base_url=self.base_url) as client:
                messages = []
                
                # Add system prompt first
                system_prompt = get_system_prompt(model_config['name'])
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
                
                # Add history
                if history:
                    for msg in history:
                        if msg.get("is_bot"):
                            messages.append({
                                "role": "assistant",
                                "content": msg["content"]
                            })
                        else:
                            if msg.get("image"):
                                messages.append({
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": msg["content"]},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64.b64encode(msg['image']).decode('utf-8')}"
                                            }
                                        }
                                    ]
                                })
                            else:
                                messages.append({
                                    "role": "user",
                                    "content": msg["content"]
                                })

                # Add current message with image if present
                if image and model_config.get('vision'):
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": message or "What's in this image?"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64.b64encode(image).decode('utf-8')}"
                                }
                            }
                        ]
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": message
                    })

                async for chunk in await client.chat.completions.create(
                    model=model_config['name'],
                    messages=messages,
                    stream=True,
                    max_tokens=self.config.max_tokens
                ):
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            logging.info("OpenAIProvider: Completed chat_completion_stream")
        except Exception as e:
            logging.error(f"OpenAIProvider Error: {e}")
            raise
