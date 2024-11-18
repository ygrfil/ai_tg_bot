from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
from bot.config import Config

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
        
        # Always start with system prompt
        formatted_messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Process history in chronological order
        if history:
            current_context = []
            for msg in history:
                if msg.get("is_bot"):
                    current_context.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
                else:
                    content = msg["content"]
                    image_data = msg.get("image")
                    
                    if image_data and self._supports_vision(model_config):
                        base64_image = base64.b64encode(image_data).decode('utf-8')
                        current_context.append(self._format_image_message(content, base64_image))
                    else:
                        current_context.append({
                            "role": "user",
                            "content": content
                        })
            formatted_messages.extend(current_context)
        
        return formatted_messages

    def _supports_vision(self, model_config: Dict[str, Any]) -> bool:
        """Check if the model supports vision features."""
        return model_config.get('vision', False)

    def _format_image_message(self, text: str, base64_image: str) -> Dict[str, Any]:
        """Default image message format - override in providers if needed."""
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
        """Get max tokens with priority:
        1. Model-specific config
        2. Global config
        3. Default fallback
        """
        return (
            model_config.get('max_tokens') or 
            self.config.max_tokens or 
            1024  # Default fallback
        )

