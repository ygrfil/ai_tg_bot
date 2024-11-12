from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class BaseAIProvider(ABC):
    """Base class for AI providers implementing common interface."""
    
    @abstractmethod
    async def generate_response(
        self, 
        prompt: str, 
        model: str, 
        history: List[Dict[str, Any]] = None,
        image: bytes = None
    ) -> str:
        """Generate a response from the AI model.
        
        Args:
            prompt: The input text to generate a response for
            model: The specific model to use for generation
            history: Optional list of previous messages
            image: Optional bytes of an image file
            
        Returns:
            The generated response text
        """
        pass

    def format_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        formatted_history = []
        for msg in history:
            role = "assistant" if msg.get("is_bot") else "user"
            content = msg["content"]
            if msg.get("image"):
                # Skip messages with images for providers that don't support them
                continue
            formatted_history.append({"role": role, "content": content})
        return formatted_history

