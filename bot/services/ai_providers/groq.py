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
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )

    async def chat_completion_stream(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        logging.info("GroqProvider: Starting chat_completion_stream")
        try:
            messages = [{
                "role": "system",
                "content": get_system_prompt(model_config['name'])
            }]
            
            # Add history
            if history:
                for msg in history:
                    if msg.get("is_bot"):
                        messages.append({
                            "role": "assistant",
                            "content": msg["content"]
                        })
                    else:
                        if msg.get("image") and model_config.get('vision', False):
                            base64_image = base64.b64encode(msg["image"]).decode('utf-8')
                            messages.append({
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": msg["content"]},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    }
                                ]
                            })
                        else:
                            messages.append({
                                "role": "user",
                                "content": msg["content"]
                            })
            
            # Add current message
            messages.append({
                "role": "user",
                "content": message
            })

            stream = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                stream=True,
                max_tokens=self._get_max_tokens(model_config),
                temperature=0.7
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logging.error(f"Groq error: {str(e)}")
            raise Exception(f"Groq error: {str(e)}")
