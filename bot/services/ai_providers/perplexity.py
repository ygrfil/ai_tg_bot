from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt

class PerplexityProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )

    async def chat_completion(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> str:
        """
        Generate a chat completion using Perplexity's API.
        Note: Perplexity doesn't support image inputs.
        """
        messages = []
        
        # Add system prompt first
        system_prompt = get_system_prompt(model_config['name'])
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Format history ensuring alternating user/assistant messages
        if history:
            # Filter out messages with images and ensure alternating roles
            formatted_history = []
            last_role = "system" if system_prompt else None
            
            for msg in history:
                current_role = "assistant" if msg.get("is_bot") else "user"
                
                # Skip if would create consecutive same roles
                if current_role == last_role:
                    continue
                    
                # Skip messages with images
                if not msg.get("is_bot") and msg.get("image"):
                    continue
                    
                formatted_history.append({
                    "role": current_role,
                    "content": msg["content"]
                })
                last_role = current_role
            
            messages.extend(formatted_history)

        # Add current message
        if last_role != "user":  # Ensure we don't add consecutive user messages
            messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Perplexity error: {str(e)}")