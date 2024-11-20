from typing import Dict, Any, List, Optional, AsyncGenerator
from openai import AsyncOpenAI
from .base import BaseAIProvider
from ...config.prompts import get_system_prompt
from ...config.settings import Config
import logging

class PerplexityProvider(BaseAIProvider):
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )

    def _format_messages(self, history: List[Dict[str, Any]], current_message: str, model_config: Dict[str, Any]) -> List[Dict[str, str]]:
        """Format message history ensuring strict user/assistant alternation."""
        messages = [{
            "role": "system",
            "content": get_system_prompt(model_config['name'])
        }]

        # Process history to ensure alternating pattern
        formatted_history = []
        for i in range(0, len(history), 2):
            # Add user message
            if i < len(history):
                user_msg = history[i]
                if not user_msg.get("is_bot"):
                    formatted_history.append({
                        "role": "user",
                        "content": user_msg["content"]
                    })

            # Add assistant message
            if i + 1 < len(history):
                assistant_msg = history[i + 1]
                if assistant_msg.get("is_bot"):
                    formatted_history.append({
                        "role": "assistant",
                        "content": assistant_msg["content"]
                    })

        # Add formatted history
        messages.extend(formatted_history)

        # Add current message
        messages.append({
            "role": "user",
            "content": current_message
        })

        return messages

    async def chat_completion_stream(
        self, 
        message: str, 
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        try:
            messages = self._format_messages(
                history or [], 
                message, 
                model_config
            )

            logging.debug(f"Formatted messages for Perplexity: {messages}")

            stream = await self.client.chat.completions.create(
                model=model_config['name'],
                messages=messages,
                temperature=0.7,
                max_tokens=self._get_max_tokens(model_config),
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_msg = f"Perplexity error: {str(e)}"
            logging.error(error_msg)
            raise Exception(error_msg)