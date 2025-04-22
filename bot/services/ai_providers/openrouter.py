from typing import Optional, List, Dict, Any, AsyncGenerator, TypedDict, cast
from dataclasses import dataclass, field
import base64
import json
import aiohttp
from .base import BaseAIProvider, ProviderConfig
from ...config import Config
import logging
import asyncio
from ..ai_providers.providers import ModelConfig

logger = logging.getLogger(__name__)

@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter provider."""
    base_url: str = "https://openrouter.ai/api/v1"
    timeout: int = 60
    temperature: float = 0.7
    referer: str = "https://github.com/your-username/your-repo"
    title: str = "AI Chat Bot"
    stream_chunk_size: int = 8192
    max_retries: int = 3
    retry_delay: float = 1.0

class OpenRouterProvider(BaseAIProvider):
    """OpenRouter API provider implementation."""

    def __init__(self, api_key: str, config: Config | None = None) -> None:
        """Initialize OpenRouter provider with API key and config."""
        super().__init__(api_key, config)
        self.config = OpenRouterConfig()
        self.model_name: str | None = None
        self.vision: bool = False

    async def chat_completion_stream(
        self,
        message: str,
        model_config: ModelConfig,
        history: list[dict[str, Any]] | None = None,
        image: bytes | None = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming chat completion response."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.config.referer,
            "X-Title": self.config.title,
        }

        messages = []
        if history:
            messages.extend(self._format_history(history, model_config))

        if image:
            base64_image = base64.b64encode(image).decode('utf-8')
            messages.append(self._format_image_message(message, base64_image))
        else:
            messages.append({"role": "user", "content": message})

        data = {
            "model": model_config['name'],
            "messages": messages,
            "stream": True,
            "temperature": self.config.temperature,
            "max_tokens": self._get_max_tokens(model_config),
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=self.config.timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error: {response.status} - {error_text}")
                        yield f"Error: OpenRouter API returned status {response.status}"
                        return

                    async for line in response.content:
                        line_text = line.decode('utf-8').strip()
                        if not line_text or line_text == "data: [DONE]":
                            continue

                        if not line_text.startswith("data: "):
                            logger.warning(f"Unexpected line format: {line_text}")
                            continue

                        try:
                            json_str = line_text[6:]  # Remove "data: " prefix
                            data = json.loads(json_str)
                            if content := data.get('choices', [{}])[0].get('delta', {}).get('content'):
                                yield content
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e} - Line: {line_text}")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing stream: {e}")
                            yield f"Error processing response: {str(e)}"
                            return

            except aiohttp.ClientError as e:
                logger.error(f"Network error: {e}")
                yield f"Network error: {str(e)}"
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                yield f"Unexpected error: {str(e)}"