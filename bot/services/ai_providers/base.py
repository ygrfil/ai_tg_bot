from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
from bot.config import Config
import re
import logging
from openai import AsyncOpenAI

class BaseAIProvider(ABC):
    """Base class for AI providers implementing common interface."""
    
    def __init__(self, config: Config):
        self.config = config
        self.system_prompt = """You are a helpful AI assistant. Maintain context of the entire conversation and provide accurate, consistent responses. Format responses using HTML tags and emojis appropriately."""

    @abstractmethod
    async def chat_completion_stream(
        self, 
        message: str,
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the AI model."""
        pass

    def _format_history(self, history: List[Dict[str, Any]], model_config: Dict[str, Any]) -> List[Dict[str, str]]:
        """Format chat history into provider-specific format."""
        formatted_messages = []
        
        # Process history in chronological order
        if history:
            for msg in history:
                # Skip any system messages in history
                if msg.get("role") == "system":
                    continue
                
                if msg.get("is_bot"):
                    formatted_messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
                else:
                    content = msg["content"]
                    image_data = msg.get("image")
                    
                    if image_data and self._supports_vision(model_config):
                        base64_image = base64.b64encode(image_data).decode('utf-8')
                        # Depending on provider, format messages appropriately
                        if model_config['name'].startswith("golq"):
                            # Groq-specific formatting
                            formatted_content = [
                                {"type": "text", "text": content},
                                {"type": "image_url", "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }}
                            ]
                        else:
                            # Default formatting
                            formatted_content = [
                                {"type": "text", "text": content},
                                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                            ]
                        
                        formatted_messages.append({
                            "role": "user",
                            "content": formatted_content
                        })
                    else:
                        formatted_messages.append({
                            "role": "user",
                            "content": content
                        })
        
        return formatted_messages

    def _supports_vision(self, model_config: Dict[str, Any]) -> bool:
        """Check if the model supports vision features."""
        return model_config.get('vision', False)

    def _format_image_message(self, text: str, base64_image: str) -> Dict[str, Any]:
        """Format image message based on provider requirements."""
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }}
            ]
        }

    def _get_max_tokens(self, model_config: Dict[str, Any]) -> int:
        """Get max tokens for the model."""
        return model_config.get('max_tokens', 4000)

