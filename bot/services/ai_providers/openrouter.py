from typing import Optional, List, Dict, Any, AsyncGenerator
import base64
import asyncio
from openai import AsyncOpenAI
from .base import BaseAIProvider
from ...config import Config
import logging

class OpenRouterProvider(BaseAIProvider):
    """OpenRouter provider using OpenAI SDK for optimal performance."""
    
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(api_key, config)
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/ygrfil/ai_tg_bot",
                "X-Title": "AI Telegram Bot"
            },
            timeout=30.0  # 30 second timeout
        )

    async def chat_completion_stream(
        self,
        message: str,
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using OpenAI SDK for optimal performance."""
        
        try:
            messages = []
            
            # Add system message
            system_prompt = self._get_system_prompt(model_config.get('name', ''))
            messages.append({"role": "system", "content": system_prompt})
            
            # Add history (limit to recent messages for speed)
            if history:
                messages.extend(self._format_history(history[-6:], model_config))  # Only last 6 messages
            
            # Add current message with image if provided
            if image and self._supports_vision(model_config):
                base64_image = base64.b64encode(image).decode('utf-8')
                messages.append(self._format_image_message(message, base64_image))
            else:
                messages.append({"role": "user", "content": message})

            # Prepare completion parameters
            completion_params = {
                "model": model_config['name'],
                "messages": messages,
                "stream": True,
                "max_tokens": 2048,  # Limit tokens for faster responses
                "temperature": 0.7,   # Slightly lower temperature for speed
            }
            
            # Add structured output if schema provided and model supports it
            if response_schema and self._supports_structured_outputs(model_config):
                completion_params["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_response",
                        "schema": response_schema,
                        "strict": True
                    }
                }
                logging.debug(f"Using structured output for model {model_config['name']}")
            
            # Create streaming completion
            stream = await self.client.chat.completions.create(**completion_params)
            
            # Stream the response
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        yield delta.content
                        
        except Exception as e:
            logging.error(f"Error in OpenRouter streaming: {e}")
            yield f"❌ Error: {str(e)}. Please try again later."

    def _supports_structured_outputs(self, model_config: Dict[str, Any]) -> bool:
        """Check if the model supports structured outputs (JSON schema)."""
        model_name = model_config.get('name', '').lower()
        
        # Models that support structured outputs via OpenRouter
        supported_models = [
            'openai/gpt-4o',
            'openai/gpt-4o-mini', 
            'openai/gpt-4-turbo',
            'anthropic/claude-3-5-sonnet',
            'anthropic/claude-3-5-haiku',
            'google/gemini-pro-1.5',
            'google/gemini-2.0-flash-exp'
        ]
        
        # Check if current model supports structured outputs
        for supported in supported_models:
            if supported in model_name:
                return True
                
        return False

    async def chat_completion_structured(
        self,
        message: str,
        model_config: Dict[str, Any],
        response_schema: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """Generate a non-streaming structured response with guaranteed JSON schema compliance."""
        
        try:
            messages = []
            
            # Add system message with structured output instruction
            system_prompt = self._get_system_prompt(model_config.get('name', ''))
            system_prompt += "\n\nIMPORTANT: You must respond with valid JSON that matches the provided schema exactly."
            messages.append({"role": "system", "content": system_prompt})
            
            # Add history (limit to recent messages for speed)
            if history:
                messages.extend(self._format_history(history[-6:], model_config))
            
            # Add current message with image if provided
            if image and self._supports_vision(model_config):
                base64_image = base64.b64encode(image).decode('utf-8')
                messages.append(self._format_image_message(message, base64_image))
            else:
                messages.append({"role": "user", "content": message})

            # Prepare completion parameters with structured output
            completion_params = {
                "model": model_config['name'],
                "messages": messages,
                "stream": False,  # Non-streaming for structured output
                "max_tokens": 2048,
                "temperature": 0.3,  # Lower temperature for more consistent JSON
            }
            
            # Add structured output schema
            if self._supports_structured_outputs(model_config):
                completion_params["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_response",
                        "schema": response_schema,
                        "strict": True
                    }
                }
            else:
                # Fallback: add JSON instruction to prompt
                messages[-1]["content"] += f"\n\nPlease respond with valid JSON matching this schema: {response_schema}"
            
            # Create completion
            response = await self.client.chat.completions.create(**completion_params)
            
            # Extract content
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                
                # Parse JSON response
                try:
                    import json
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON response: {e}")
                    # Return error in expected format
                    return {
                        "response_type": "error",
                        "content": f"Failed to generate valid structured response: {str(e)}",
                        "confidence": 0.0,
                        "error_type": "unclear_request",
                        "suggestion": "Please try rephrasing your request",
                        "can_retry": True
                    }
            else:
                raise Exception("No response received from model")
                
        except Exception as e:
            logging.error(f"Error in structured completion: {e}")
            return {
                "response_type": "error",
                "content": f"Error generating response: {str(e)}",
                "confidence": 0.0,
                "error_type": "unclear_request", 
                "suggestion": "Please try again later",
                "can_retry": True
            }