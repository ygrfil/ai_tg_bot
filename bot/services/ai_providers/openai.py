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
                messages = self._format_history(history, model_config)
                
                if image and model_config.get('vision'):
                    if len(image) > 4 * 1024 * 1024:
                        raise Exception("Image size exceeds 4MB limit")
                    base64_image = base64.b64encode(image).decode('utf-8')
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": message or "What's in this image?"},
                            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                        ]
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": message
                    })
                
                response = await client.chat.completions.create(
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
            logging.info("OpenAIProvider: Completed chat_completion_stream")
        except Exception as e:
            logging.error(f"OpenAIProvider Error: {e}")
            raise
