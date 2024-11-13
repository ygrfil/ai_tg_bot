from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncGenerator
import base64

class BaseAIProvider(ABC):
    """Base class for AI providers implementing common interface."""
    
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
        
        for msg in history:
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
                    if isinstance(content, str):
                        formatted_messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": content},
                                {"type": "image_url", "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }}
                            ]
                        })
                else:
                    formatted_messages.append({
                        "role": "user",
                        "content": content
                    })
        
        return formatted_messages

    def _supports_vision(self, model_config: Dict[str, Any]) -> bool:
        """Check if the current model configuration supports vision."""
        return model_config.get('vision', False)

