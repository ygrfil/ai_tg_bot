from groq import AsyncGroq
from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
from .base import BaseAIProvider
from ...config.settings import Config
from ...config.prompts import get_system_prompt

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
        try:
            messages = []
            
            # Don't add system prompt when using vision
            if not image:
                system_prompt = get_system_prompt(model_config['name'])
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})

            # Process history (excluding images from history when new image is present)
            if history:
                for msg in history:
                    if msg.get("is_bot"):
                        messages.append({
                            "role": "assistant",
                            "content": msg["content"]
                        })
                    else:
                        content = msg["content"]
                        # Skip images from history if we have a new image
                        if not image or not msg.get("image"):
                            messages.append({
                                "role": "user",
                                "content": content
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

            # Create completion with exact parameters from documentation
            response = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                top_p=1,
                stream=True
            )

            # Handle streaming response correctly
            async for chunk in response:
                if hasattr(chunk.choices[0].delta, 'content'):
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                    
        except Exception as e:
            error_msg = str(e)
            if "413" in error_msg:
                raise Exception("Image size exceeds Groq's 4MB limit")
            elif "400" in error_msg:
                raise Exception("Invalid request format or multiple images detected")
            else:
                raise Exception(f"Groq error: {error_msg}")
