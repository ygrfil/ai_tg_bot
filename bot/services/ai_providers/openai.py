from openai import AsyncOpenAI
import base64
from typing import Optional, List, Dict, Any
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt

class OpenAIProvider(BaseAIProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

    async def chat_completion(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        messages = []
        system_prompt = get_system_prompt(model_config['name'])
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if history:
            for msg in history:
                if msg.get("is_bot"):
                    messages.append({"role": "assistant", "content": msg["content"]})
                else:
                    content = msg["content"]
                    img_data = msg.get("image")
                    
                    if img_data and model_config.get('vision'):
                        base64_image = base64.b64encode(img_data).decode('utf-8')
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": content},
                                {"type": "image_url", "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }}
                            ]
                        })
                    else:
                        messages.append({"role": "user", "content": content})
        
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
            messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI error: {str(e)}")
