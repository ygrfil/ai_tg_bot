from typing import Optional, List, Dict, Any, AsyncGenerator
from anthropic import AsyncAnthropic
import base64
import logging
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt
from ...config.settings import Config

class ClaudeProvider(BaseAIProvider):
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(config)
        self.client = AsyncAnthropic(api_key=api_key)
        
    async def chat_completion_stream(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
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
            system_prompt = self._get_system_prompt(model_config['name'])
            
            stream = await self.client.messages.create(
                model=model_config['name'],
                messages=messages,
                system=system_prompt,
                max_tokens=self._get_max_tokens(model_config),
                stream=True
            )
            
            async for chunk in stream:
                # Handle different types of streaming responses
                if hasattr(chunk, 'type'):
                    if chunk.type == 'content_block_start':
                        continue
                    elif chunk.type == 'content_block_delta':
                        if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                            yield chunk.delta.text
                    elif chunk.type == 'message_delta':
                        if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'content'):
                            yield chunk.delta.content
                elif hasattr(chunk, 'content'):
                    # Handle non-streaming response format
                    yield chunk.content
                    
        except Exception as e:
            logging.error(f"Claude error: {str(e)}", exc_info=True)
            raise Exception(f"Claude error: {str(e)}")