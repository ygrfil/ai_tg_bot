import logging
from typing import List, Dict, Any
from openai import OpenAI
from anthropic import Anthropic
from config import MODEL_CONFIG, ENV

logger = logging.getLogger(__name__)

Message = Dict[str, str]

def get_llm(selected_model: str):
    logger.info(f"Initializing LLM for model: {selected_model}")
    
    model_configs = {
        "openai": OpenAI,
        "anthropic": Anthropic,
        "perplexity": lambda **kwargs: OpenAI(base_url="https://api.perplexity.ai", **kwargs),
        "groq": lambda **kwargs: OpenAI(base_url="https://api.groq.com/openai/v1", **kwargs),
        "hyperbolic": lambda **kwargs: OpenAI(base_url="https://api.hyperbolic.ai/v1", **kwargs),
        "gemini": lambda **kwargs: OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta", **kwargs),
    }
    
    if selected_model not in model_configs:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    api_key = ENV.get(f"{selected_model.upper()}_API_KEY")
    if not api_key:
        logger.warning(f"API key for {selected_model} is not set. Please check your environment variables.")
        return None
    
    client = model_configs[selected_model](api_key=api_key)
    
    if selected_model == "anthropic":
        return lambda **kwargs: handle_anthropic_response(client.messages.create(**kwargs))
    elif selected_model == "perplexity":
        return lambda **kwargs: client.chat.completions.create(**prepare_perplexity_messages(kwargs))
    else:
        return client.chat.completions.create

def handle_anthropic_response(response):
    class AnthropicResponse:
        def __init__(self, content):
            self.choices = [type('obj', (object,), {'delta': type('obj', (object,), {'content': content})()})]

    return AnthropicResponse(response.content)

def prepare_perplexity_messages(kwargs):
    messages = kwargs.get('messages', [])
    if messages and messages[0]['role'] == 'system':
        system_message = messages.pop(0)
        messages.insert(0, {'role': 'user', 'content': f"System: {system_message['content']}"})
    kwargs['messages'] = messages
    return kwargs

def get_conversation_messages(user_conversation_history: Dict[int, List[Message]], user_id: int) -> List[Message]:
    messages = user_conversation_history[user_id]
    return messages[:-1] if messages and messages[-1]["role"] == "assistant" else messages
