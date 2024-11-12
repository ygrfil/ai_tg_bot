from typing import Optional, List, Dict, Any
from anthropic import AsyncAnthropic
import base64
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt

class ClaudeProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        
    async def generate_response(
        self, 
        prompt: str, 
        model: str,
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        formatted_messages = []
        system_prompt = get_system_prompt(model)
        
        # Format history if provided
        if history:
            for msg in history:
                if msg.get("is_bot"):
                    formatted_messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
                else:
                    if msg.get("image"):
                        # Convert bytes to base64 string if it's not already
                        image_data = msg["image"]
                        if isinstance(image_data, bytes):
                            image_data = base64.b64encode(image_data).decode('utf-8')
                        
                        formatted_messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": image_data
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": msg["content"]
                                }
                            ]
                        })
                    else:
                        formatted_messages.append({
                            "role": "user",
                            "content": msg["content"]
                        })

        # Add current message
        if image:
            # Convert current image bytes to base64 string
            image_data = base64.b64encode(image).decode('utf-8')
            
            formatted_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            })
        else:
            formatted_messages.append({
                "role": "user",
                "content": prompt
            })

        response = await self.client.messages.create(
            model=model,
            max_tokens=4096,
            messages=formatted_messages,
            system=system_prompt
        )
        
        return response.content[0].text