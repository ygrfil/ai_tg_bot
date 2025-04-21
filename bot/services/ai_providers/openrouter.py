from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
import json
import aiohttp
from .base import BaseAIProvider
from ...config import Config
import logging
import asyncio

class OpenRouterProvider(BaseAIProvider):
    """OpenRouter provider that handles all AI models."""
    
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(api_key, config)
        self.base_url = "https://openrouter.ai/api/v1"
        self.model_name = None
        self.vision = False

    async def chat_completion_stream(
        self,
        message: str,
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from OpenRouter."""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourgithub/ai_tg_bot",
            "X-Title": "AI Telegram Bot"
        }

        messages = []
        
        # Add system message
        system_prompt = self._get_system_prompt(model_config.get('name', ''))
        messages.append({"role": "system", "content": system_prompt})
        
        # Add history
        if history:
            messages.extend(self._format_history(history, model_config))
        
        # Add current message with image if provided
        if image and self._supports_vision(model_config):
            base64_image = base64.b64encode(image).decode('utf-8')
            messages.append(self._format_image_message(message, base64_image))
        else:
            messages.append({"role": "user", "content": message})

        data = {
            "model": model_config['name'],
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 2000
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"OpenRouter API error: {error_text}")
                        yield f"Error: {error_text}"
                        return

                    # Process the stream
                    buffer = ""
                    async for line in response.content:
                        if line:
                            try:
                                line = line.decode('utf-8').strip()
                                if line.startswith('data: '):
                                    line = line[6:]  # Remove 'data: ' prefix
                                if line and line != '[DONE]':
                                    try:
                                        chunk = json.loads(line)
                                        if chunk.get('choices') and len(chunk['choices']) > 0:
                                            content = chunk['choices'][0].get('delta', {}).get('content', '')
                                            if content:
                                                buffer += content
                                                # Yield complete sentences or accumulated content
                                                while '.' in buffer or '\n' in buffer:
                                                    split_char = '.' if '.' in buffer else '\n'
                                                    parts = buffer.split(split_char, 1)
                                                    if len(parts) > 1:
                                                        yield parts[0] + split_char
                                                        buffer = parts[1]
                                                    else:
                                                        break
                                    except json.JSONDecodeError:
                                        continue
                            except Exception as e:
                                logging.error(f"Error processing chunk: {e}")
                                continue

                    # Yield any remaining content in buffer
                    if buffer:
                        yield buffer

        except asyncio.TimeoutError:
            logging.error("OpenRouter API timeout")
            yield "Error: Request timed out. Please try again."
        except Exception as e:
            logging.error(f"OpenRouter API error: {e}")
            yield f"Error: An unexpected error occurred. Please try again."