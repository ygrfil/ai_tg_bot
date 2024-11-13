from typing import Optional, List, Dict, Any
from anthropic import AsyncAnthropic
import base64
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt

class ClaudeProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        
    async def chat_completion(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        messages = []
        
        if history:
            for msg in history:
                if msg.get("is_bot"):
                    messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
                else:
                    content = msg["content"]
                    img_data = msg.get("image")
                    
                    if img_data and model_config.get('vision'):
                        base64_image = base64.b64encode(img_data).decode('utf-8')
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "image", "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image
                                }},
                                {"type": "text", "text": content}
                            ]
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": content
                        })
        
        # Add current message with image if present
        if image and model_config.get('vision'):
            base64_image = base64.b64encode(image).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_image
                    }},
                    {"type": "text", "text": message}
                ]
            })
        else:
            messages.append({
                "role": "user",
                "content": message
            })

        try:
            response = await self.client.messages.create(
                model=model_config['name'],
                messages=messages,
                max_tokens=1000
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Claude error: {str(e)}")