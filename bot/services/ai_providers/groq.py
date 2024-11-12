import base64
from groq import AsyncGroq
from typing import Optional, List, Dict, Any
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt

class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncGroq(api_key=api_key)
        
    async def generate_response(
        self, 
        prompt: str, 
        model: str,
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        messages = [{"role": "system", "content": get_system_prompt(model)}]
        has_image = False  # Track if we've already included an image
        
        # Format history if provided
        if history:
            for msg in history:
                if msg.get("is_bot"):
                    messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
                else:
                    if msg.get("image") and not has_image and not image:
                        # Only include the most recent image from history if no new image
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
                        has_image = True
                    else:
                        # For non-image messages or if we already have an image
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
            messages.append({
                "role": "user",
                "content": prompt
            })

        # Make API call
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            stream=False
        )
        
        return response.choices[0].message.content
