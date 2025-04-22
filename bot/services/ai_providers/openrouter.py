from typing import Optional, List, Dict, Any, AsyncGenerator, TypedDict, cast
from dataclasses import dataclass, field
import base64
import json
import aiohttp
from .base import BaseAIProvider, ProviderConfig
from ...config import Config
import logging
import asyncio
from ..ai_providers.providers import ModelConfig, PROVIDER_MODELS

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
    default_model: str = "openai"  # Default to OpenAI model if none specified
    max_history_size: int = 20  # Maximum number of messages to keep in history

class OpenRouterProvider(BaseAIProvider):
    """OpenRouter API provider implementation."""

    # Config attribute names for persistence
    CONFIG_KEY_MODEL = "openrouter_current_model"
    CONFIG_KEY_HISTORY = "openrouter_conversation_history"

    # Known OpenRouter status messages that should not trigger warnings
    _KNOWN_STATUS_MESSAGES = {
        ": OPENROUTER PROCESSING",
        ": OPENROUTER QUEUED",
        "data: [DONE]",
        ""
    }

    def __init__(self, api_key: str, config: Config | None = None) -> None:
        """Initialize OpenRouter provider with API key and config."""
        super().__init__(api_key, config)
        self.config = OpenRouterConfig()
        self._current_model: ModelConfig | None = None
        self._conversation_history: list[dict[str, Any]] = []
        self._user_config = config
        
        # Load saved state from config if available
        if config:
            self._load_state_from_config()
        else:
            self._initialize_default_model()

        logger.info(f"OpenRouterProvider initialized with model: {self._current_model['name'] if self._current_model else 'None'}")
        logger.info(f"Conversation history loaded: {len(self._conversation_history)} messages")

    def _load_state_from_config(self) -> None:
        """Load saved state from config."""
        # Load model
        saved_model = getattr(self._user_config, self.CONFIG_KEY_MODEL, None)
        if saved_model and saved_model in PROVIDER_MODELS:
            self._current_model = PROVIDER_MODELS[saved_model]
            logger.info(f"Loaded saved model from config: {saved_model}")
        else:
            self._initialize_default_model()

        # Load conversation history
        saved_history = getattr(self._user_config, self.CONFIG_KEY_HISTORY, [])
        if isinstance(saved_history, list):
            self._conversation_history = saved_history
            logger.info(f"Loaded {len(saved_history)} messages from conversation history")
        else:
            logger.warning("Invalid conversation history format in config")
            self._conversation_history = []

    def _save_state_to_config(self) -> None:
        """Save current state to config."""
        if not self._user_config:
            logger.warning("No config available to save state")
            return

        # Save current model
        if self._current_model:
            for key, model in PROVIDER_MODELS.items():
                if model['name'] == self._current_model['name']:
                    setattr(self._user_config, self.CONFIG_KEY_MODEL, key)
                    break

        # Save conversation history
        setattr(self._user_config, self.CONFIG_KEY_HISTORY, self._conversation_history)
        logger.debug(f"Saved state to config: model={self._current_model['name'] if self._current_model else 'None'}, history_size={len(self._conversation_history)}")

    def _initialize_default_model(self) -> None:
        """Initialize the default model to ensure we always have a model selected."""
        if self._current_model is None:
            default_model = PROVIDER_MODELS.get(self.config.default_model)
            if default_model is None:
                # Fallback to first available model if default is not found
                default_model = next(iter(PROVIDER_MODELS.values()))
            self._current_model = default_model
            logger.info(f"Initialized default model: {self._current_model['name']}")
            self._save_state_to_config()

    def set_model(self, model_key: str) -> None:
        """Set the current model configuration."""
        if model_key not in PROVIDER_MODELS:
            logger.warning(f"Invalid model key '{model_key}', using default model")
            self._initialize_default_model()
            return

        if self._current_model and self._current_model['name'] == PROVIDER_MODELS[model_key]['name']:
            logger.debug(f"Model {model_key} already selected")
            return

        self._current_model = PROVIDER_MODELS[model_key]
        logger.info(f"Model set to: {self._current_model['name']}")
        self._save_state_to_config()

    def get_current_model(self) -> ModelConfig:
        """Get the current model configuration, initializing default if none set."""
        if self._current_model is None:
            self._initialize_default_model()
        return cast(ModelConfig, self._current_model)

    def _update_conversation_history(self, role: str, content: str | list[dict[str, Any]]) -> None:
        """Update the conversation history with a new message."""
        message = {"role": role, "content": content}
        self._conversation_history.append(message)
        
        # Keep only last N messages to prevent context overflow
        if len(self._conversation_history) > self.config.max_history_size:
            self._conversation_history = self._conversation_history[-self.config.max_history_size:]
        
        # Save after each update
        self._save_state_to_config()
        logger.debug(f"Updated conversation history: {len(self._conversation_history)} messages")

    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        self._conversation_history = []
        self._save_state_to_config()
        logger.info("Conversation history cleared")

    def _handle_stream_line(self, line_text: str) -> str | None:
        """Handle a single line from the stream and return content if available."""
        if line_text in self._KNOWN_STATUS_MESSAGES:
            if line_text and not line_text.startswith("data:"):
                logger.debug(f"OpenRouter status: {line_text}")
            return None

        if not line_text.startswith("data: "):
            if line_text:  # Only log if there's actual content
                logger.warning(f"Unexpected line format: {line_text}")
            return None

        try:
            json_str = line_text[6:]  # Remove "data: " prefix
            data = json.loads(json_str)
            return data.get('choices', [{}])[0].get('delta', {}).get('content')
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e} - Line: {line_text}")
        except Exception as e:
            logger.error(f"Error processing stream data: {e}")
        return None

    def _format_history(
        self,
        history: list[dict[str, Any]],
        model_config: ModelConfig
    ) -> list[dict[str, Any]]:
        """Format conversation history for the model."""
        formatted_history = []
        
        for msg in history:
            if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                logger.warning(f"Skipping invalid message in history: {msg}")
                continue
                
            role = msg['role']
            content = msg['content']
            
            # Validate role
            if role not in ['system', 'user', 'assistant']:
                logger.warning(f"Invalid role in message: {role}")
                continue
            
            # Handle different content types
            if isinstance(content, list):
                # Handle messages with multiple content parts (like images)
                formatted_content = []
                for part in content:
                    if isinstance(part, dict) and 'type' in part:
                        if part['type'] == 'text':
                            formatted_content.append(part)
                        elif part['type'] == 'image_url' and model_config.get('vision', False):
                            formatted_content.append(part)
                if formatted_content:
                    formatted_history.append({
                        "role": role,
                        "content": formatted_content
                    })
            elif isinstance(content, str):
                # Handle simple text messages
                if content.strip():  # Only add non-empty messages
                    formatted_history.append({
                        "role": role,
                        "content": content
                    })
            else:
                logger.warning(f"Skipping message with invalid content type: {type(content)}")
                
        logger.debug(f"Formatted {len(formatted_history)} messages from history")
        return formatted_history

    def _convert_to_role_format(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert history from storage format (is_bot) to role format."""
        converted_history = []
        
        for msg in history:
            if not isinstance(msg, dict):
                logger.warning(f"Skipping non-dict history item: {msg}")
                continue
                
            # Handle storage format with is_bot
            if 'is_bot' in msg and 'content' in msg:
                is_bot = msg['is_bot']
                role = "assistant" if is_bot else "user"
                content = msg['content']
                
                # Add to converted history
                converted_history.append({
                    "role": role,
                    "content": content
                })
                logger.debug(f"Converted history message: {role} - {content[:20]}...")
            # Handle already formatted messages
            elif 'role' in msg and 'content' in msg:
                converted_history.append(msg)
            else:
                logger.warning(f"Skipping invalid message format: {msg}")
                
        return converted_history

    async def chat_completion_stream(
        self,
        message: str,
        model_config: ModelConfig,
        history: list[dict[str, Any]] | None = None,
        image: bytes | None = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming chat completion response."""
        # Update current model state if different
        if not self._current_model or self._current_model['name'] != model_config['name']:
            self._current_model = model_config
            logger.info(f"Updated model to: {model_config['name']}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.config.referer,
            "X-Title": self.config.title,
        }

        # Prepare messages array with system prompt
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(model_config['name'])
            }
        ]

        # Add conversation history
        if history:
            # Check for is_bot format and convert if needed
            if any('is_bot' in msg for msg in history if isinstance(msg, dict)):
                logger.info("Converting history from storage format to role format")
                converted_history = self._convert_to_role_format(history)
                formatted_history = self._format_history(converted_history, model_config)
                messages.extend(formatted_history)
                # Update internal history
                self._conversation_history = formatted_history
            else:
                # If external history is provided, use it and update our internal history
                formatted_history = self._format_history(history, model_config)
                messages.extend(formatted_history)
                self._conversation_history = formatted_history
        else:
            # Use our internal conversation history
            messages.extend(self._conversation_history)

        # Add current message
        if image:
            if not model_config.get('vision', False):
                logger.error(f"Model {model_config['name']} does not support vision")
                yield "Error: Current model does not support image processing"
                return
            base64_image = base64.b64encode(image).decode('utf-8')
            current_message = self._format_image_message(message, base64_image)
        else:
            current_message = {"role": "user", "content": message}
        
        messages.append(current_message)
        
        # Update history with user message
        self._update_conversation_history("user", current_message["content"])

        data = {
            "model": model_config['name'],
            "messages": messages,
            "stream": True,
            "temperature": self.config.temperature,
            "max_tokens": self._get_max_tokens(model_config),
        }

        logger.debug(f"Sending request with {len(messages)} messages in context")

        accumulated_response = []
        retry_count = 0
        while retry_count < self.config.max_retries:
            try:
                async with aiohttp.ClientSession() as session:
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
                            if content := self._handle_stream_line(line_text):
                                accumulated_response.append(content)
                                yield content

                        # Update history with assistant's complete response
                        if accumulated_response:
                            complete_response = "".join(accumulated_response)
                            self._update_conversation_history("assistant", complete_response)
                            logger.debug(f"Added assistant response to history (length: {len(complete_response)})")
                        return

            except aiohttp.ClientError as e:
                retry_count += 1
                if retry_count >= self.config.max_retries:
                    logger.error(f"Network error after {retry_count} retries: {e}")
                    yield f"Network error: {str(e)}"
                    return
                logger.warning(f"Network error (attempt {retry_count}): {e}")
                await asyncio.sleep(self.config.retry_delay)

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                yield f"Unexpected error: {str(e)}"
                return