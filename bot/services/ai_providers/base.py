from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Protocol, TypeVar, cast
from dataclasses import dataclass, field
from bot.config import Config
from bot.config.prompts import get_system_prompt
import re
import logging
from openai import AsyncOpenAI
from .providers import ModelConfig, PROVIDER_MODELS

T = TypeVar('T', bound='BaseAIProvider')

@dataclass
class ProviderConfig:
    """Base configuration for AI providers."""
    system_prompts: dict[str, str] = field(default_factory=lambda: {
        "default": "You are a helpful AI assistant.",
        "gpt-4-vision-preview": "You are a helpful AI assistant capable of understanding and discussing images.",
        "claude-3-opus": "You are Claude, a helpful AI assistant created by Anthropic.",
        "claude-3-sonnet": "You are Claude, a helpful AI assistant created by Anthropic.",
        "gemini-pro": "You are Gemini, a helpful AI assistant created by Google.",
        "gemini-pro-vision": "You are Gemini, a helpful AI assistant capable of understanding and discussing images."
    })

class BaseAIProvider(ABC):
    """Base class for AI providers."""

    def __init__(self, api_key: str, config: Config | None = None) -> None:
        """Initialize the provider with API key and optional config."""
        self.api_key = api_key
        self.config = config or Config()
        self.provider_config = ProviderConfig()

    def _get_system_prompt(self, model_name: str) -> str:
        """Get the appropriate system prompt for the model."""
        return self.provider_config.system_prompts.get(
            model_name,
            self.provider_config.system_prompts["default"]
        )

    def _supports_vision(self, model_config: ModelConfig) -> bool:
        """Check if the model supports vision capabilities."""
        return bool(model_config.get('image_generation', False))

    def _format_history(
        self,
        history: list[dict[str, Any]],
        model_config: ModelConfig
    ) -> list[dict[str, Any]]:
        """Format conversation history for the model."""
        formatted_history = []
        for msg in history:
            if msg.get('role') and msg.get('content'):
                formatted_history.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
        return formatted_history

    def _format_image_message(self, text: str, base64_image: str) -> dict[str, Any]:
        """Format a message containing both text and image."""
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }

    @abstractmethod
    async def chat_completion_stream(
        self,
        message: str,
        model_config: ModelConfig,
        history: list[dict[str, Any]] | None = None,
        image: bytes | None = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming chat completion response."""
        raise NotImplementedError

    def _get_max_tokens(self, model_config: ModelConfig) -> int:
        """Get max tokens for the model."""
        return model_config.get('max_tokens', 4000)
