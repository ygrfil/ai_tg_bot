from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Protocol, TypeVar, cast
from dataclasses import dataclass, field
from bot.config import Config
from bot.config.prompts import get_system_prompt, uses_system_prompt_parameter, needs_system_prompt
import re
import logging
from openai import AsyncOpenAI
from .providers import ModelConfig, PROVIDER_MODELS

T = TypeVar('T', bound='BaseAIProvider')

@dataclass
class ProviderConfig:
    """Base configuration for AI providers."""
    # No need for system_prompts here - we'll use the centralized one from prompts.py

class BaseAIProvider(ABC):
    """Base class for AI providers."""

    def __init__(self, api_key: str, config: Config | None = None) -> None:
        """Initialize the provider with API key and optional config."""
        self.api_key = api_key
        self.config = config or Config()
        self.provider_config = ProviderConfig()
        self.provider_name = self.__class__.__name__.replace('Provider', '').lower()

    def _get_system_prompt(self, model_name: str) -> str:
        """Get the appropriate system prompt for the model."""
        # Use the centralized system prompt from prompts.py
        return get_system_prompt(model_name)
    
    def _add_system_prompt(self, data: dict[str, Any], model_name: str, messages: list[dict[str, Any]]) -> None:
        """
        Add system prompt to either data parameters or messages based on provider requirements.
        
        Args:
            data: The request data dictionary to be modified
            model_name: Name of the model being used
            messages: Messages array that might need the system prompt
            
        Returns:
            None (modifies data and/or messages in place)
        """
        # Skip if this provider doesn't need a system prompt (e.g., image generation)
        if not needs_system_prompt(self.provider_name):
            logging.debug(f"Skipping system prompt for {self.provider_name}")
            return
            
        system_prompt = self._get_system_prompt(model_name)
        
        if uses_system_prompt_parameter(self.provider_name):
            # Add as a parameter to the request data
            data["system_prompt"] = system_prompt
            logging.debug(f"Added system_prompt as parameter for {self.provider_name}")
        else:
            # Add as a message to the messages array
            if not any(msg.get('role') == 'system' for msg in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": system_prompt
                })
                logging.debug(f"Added system prompt as message for {self.provider_name}")

    def _supports_vision(self, model_config: ModelConfig) -> bool:
        """Check if the model supports vision capabilities."""
        return bool(model_config.get('vision', False))  # Fixed to use vision instead of image_generation

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
        return model_config.get('max_output_tokens', 4000)  # Fixed to use max_output_tokens from model_config
