import logging
from typing import List, Dict, Any, Optional, Callable
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
from config import MODEL_CONFIG, ENV

logger = logging.getLogger(__name__)

Message = Dict[str, str]

def get_llm(selected_model: str) -> Optional[Callable]:
    logger.info(f"Initializing LLM for model: {selected_model}")
    
    model_configs = {
        "openai": OpenAI,
        "anthropic": Anthropic,
        "perplexity": lambda **kwargs: OpenAI(base_url="https://api.perplexity.ai", **kwargs),
        "groq": lambda **kwargs: OpenAI(base_url="https://api.groq.com/openai/v1", **kwargs),
        "hyperbolic": lambda **kwargs: OpenAI(base_url="https://api.hyperbolic.ai/v1", **kwargs),
        "gemini": genai,
    }
    
    if selected_model not in model_configs:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    api_key = ENV.get(f"{selected_model.upper()}_API_KEY")
    if not api_key:
        logger.warning(f"API key for {selected_model} is not set. Please check your environment variables.")
        return None
    
    if selected_model == "gemini":
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_CONFIG['gemini_model'])
        return lambda **kwargs: handle_gemini_response(model.generate_content(**prepare_gemini_messages(kwargs)))
    
    client = model_configs[selected_model](api_key=api_key)
    
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

def handle_gemini_response(response):
    class GeminiResponse:
        def __init__(self, content):
            self.choices = [type('obj', (object,), {'delta': type('obj', (object,), {'content': content})()})]

    return GeminiResponse(response.text)

def prepare_anthropic_messages(kwargs):
    messages = kwargs.get('messages', [])
    system_message = next((m['content'] for m in messages if m['role'] == 'system'), None)
    
    # Convert messages to Anthropic format
    anthropic_messages = []
    for message in messages:
        if message['role'] != 'system':
            anthropic_messages.append({
                'role': 'user' if message['role'] == 'user' else 'assistant',
                'content': message['content']
            })
    
    # Prepare kwargs for Anthropic API
    model = MODEL_CONFIG.get('anthropic_model', 'claude-3-opus-20240229')
    max_tokens = int(MODEL_CONFIG.get('anthropic_max_tokens', 1024))
    
    return {
        'model': model,
        'max_tokens': max_tokens,
        'system': system_message,
        'messages': anthropic_messages
    }

def prepare_gemini_messages(kwargs):
    messages = kwargs.get('messages', [])
    prompt_parts = []
    
    for message in messages:
        if message['role'] == 'system':
            prompt_parts.append(f"System: {message['content']}")
        elif message['role'] == 'user':
            prompt_parts.append(f"Human: {message['content']}")
        elif message['role'] == 'assistant':
            prompt_parts.append(f"Assistant: {message['content']}")
    
    kwargs['contents'] = "\n".join(prompt_parts)
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
