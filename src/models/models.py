import logging
from typing import List, Dict, Optional, Callable, TypedDict
from openai import OpenAI
from anthropic import Anthropic
from config import MODEL_CONFIG, ENV

logger = logging.getLogger(__name__)

class Message(TypedDict):
    role: str
    content: str

MODEL_CONFIGS = {
    "openai": lambda api_key: OpenAI(api_key=api_key),
    "anthropic": lambda api_key: Anthropic(api_key=api_key),
    "perplexity": lambda api_key: OpenAI(api_key=api_key, base_url="https://api.perplexity.ai"),  # Perplexity API
    "groq": lambda api_key: OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")    # Groq API
}

def get_llm(selected_model: str) -> Optional[Callable]:
    """Initialize and return an LLM client."""
    logger.info(f"Initializing LLM for model: {selected_model}")
    
    if selected_model not in MODEL_CONFIGS:
        logger.error(f"Unknown model: {selected_model}")
        return None
    
    if MODEL_CONFIGS[selected_model] is None:
        logger.error(f"Model {selected_model} is not yet implemented")
        return None
    
    api_key = ENV.get(f"{selected_model.upper()}_API_KEY")
    if not api_key:
        logger.warning(f"API key for {selected_model} is not set. Please check your environment variables.")
        return None
    
    client = MODEL_CONFIGS[selected_model](api_key) if callable(MODEL_CONFIGS[selected_model]) else MODEL_CONFIGS[selected_model](api_key=api_key)
    
    if selected_model == "anthropic":
        return lambda **kwargs: handle_anthropic_response(client.messages.create(**prepare_anthropic_messages(kwargs)))
    elif selected_model == "perplexity":
        return lambda **kwargs: client.chat.completions.create(**prepare_perplexity_messages(kwargs))
    else:
        return client.chat.completions.create

def handle_anthropic_response(response):
    class AnthropicResponse:
        def __init__(self, content):
            self.choices = [type('obj', (object,), {'delta': type('obj', (object,), {'content': content})()})]

    return AnthropicResponse(response.content[0].text)


def prepare_anthropic_messages(kwargs):
    messages = kwargs.get('messages', [])
    system_message = next((m['content'] for m in messages if m['role'] == 'system'), None)
    
    # Convert messages to Anthropic format
    anthropic_messages = []
    for message in messages:
        if message['role'] == 'system':
            continue  # Skip system message as it's handled separately
            
        if isinstance(message['content'], list):
            # Already in correct format for images
            content = message['content']
        else:
            # Convert text to content list format
            content = [{'type': 'text', 'text': message['content']}]
            
        anthropic_messages.append({
            'role': 'user' if message['role'] == 'user' else 'assistant',
            'content': content
        })
    
    # Prepare kwargs for Anthropic API
    model = MODEL_CONFIG.get('anthropic_model', 'claude-3-opus-20240229')
    max_tokens = int(MODEL_CONFIG.get('anthropic_max_tokens', 1024))
    
    kwargs = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': anthropic_messages
    }
    
    # Add system message if present
    if system_message:
        kwargs['system'] = system_message
        
    return kwargs


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
