from openai import AsyncOpenAI
from .base import BaseAIProvider
import base64
from typing import List, Dict, Any
from ...config.prompts import get_system_prompt

class OpenAIProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        
    async def generate_response(
        self, 
        prompt: str, 
        model: str, 
        history: List[Dict[str, Any]] = None,
        image: bytes = None
    ) -> str:
        messages = [{"role": "system", "content": get_system_prompt(model)}]
        
        # Format history if provided
        if history:
            for msg in history:
                if msg.get("is_bot"):
                    messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
                else:
                    if msg.get("image"):
                        # Image is already base64 encoded in history
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": msg["content"]},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{msg['image']}"
                                    }
                                }
                            ]
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": msg["content"]
                        })
        
        # Handle current message
        if image:
            base64_image = base64.b64encode(image).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            })
        else:
            messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content
