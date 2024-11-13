from openai import AsyncOpenAI
import base64
from typing import Optional, List, Dict, Any
from .base import BaseAIProvider

class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )

    async def chat_completion(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        messages = []
        
        # Format history without images first
        if history:
            for msg in history:
                if msg.get("is_bot"):
                    messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
                else:
                    # Skip messages with images in history
                    if not msg.get("image"):
                        messages.append({
                            "role": "user",
                            "content": msg["content"]
                        })
        
        # Add current message with image if present
        if image and model_config.get('vision'):
            base64_image = base64.b64encode(image).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
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

        try:
            response = await self.client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",  # Using the more capable vision model
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Groq error: {str(e)}")
