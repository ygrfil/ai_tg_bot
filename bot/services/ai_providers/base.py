from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class BaseAIProvider(ABC):
    """Base class for AI providers implementing common interface."""
    
    @abstractmethod
    async def chat_completion(
        self, 
        message: str,
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        """Generate a response from the AI model."""
        pass

    def _format_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format chat history into provider-specific format."""
        return [
            {"role": "assistant" if msg.get("is_bot") else "user", "content": msg["content"]} 
            for msg in history if not msg.get("image")
        ]

