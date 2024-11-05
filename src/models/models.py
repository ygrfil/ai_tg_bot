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
    "perplexity": lambda api_key: OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai",
        default_headers={
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    ),
    "groq": lambda api_key: OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
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
    
    # Convert messages to Perplexity format
    perplexity_messages = []
    for message in messages:
        if message['role'] == 'system':
            perplexity_messages.append({
                'role': 'user',
                'content': f"System: {message['content']}"
            })
        else:
            if isinstance(message.get('content'), list):
                text_content = next((item['text'] for item in message['content'] 
                                   if isinstance(item, dict) and item.get('type') == 'text'), '')
                perplexity_messages.append({
                    'role': message['role'],
                    'content': text_content
                })
            else:
                perplexity_messages.append(message)
    
    # Update kwargs with formatted messages
    kwargs['messages'] = perplexity_messages
    
    # Read supported parameters from MODEL_CONFIG
    kwargs.update({
        'model': MODEL_CONFIG.get('perplexity_model', 'pplx-70b-online'),
        'max_tokens': int(MODEL_CONFIG.get('perplexity_max_tokens', 1024)),
        'temperature': float(MODEL_CONFIG.get('perplexity_temperature', 0.7)),
        'top_p': float(MODEL_CONFIG.get('perplexity_top_p', 0.9))
    })
    
    return kwargs


def get_conversation_messages(conversation_history: Dict[int, List[Dict]], user_id: int) -> List[Dict]:
    """Get formatted conversation messages for the specified user."""
    if user_id not in conversation_history:
        return []
    
    messages = conversation_history[user_id]
    
    # If the last message is from the assistant, exclude it
    if messages and messages[-1]['role'] == 'assistant':
        messages = messages[:-1]
    
    return messages

def format_messages_for_model(messages: List[Dict], model: str) -> List[Dict]:
    formatted_messages = []
    for msg in messages:
        if msg['role'] == 'system':
            formatted_messages.append(msg)
            continue
            
        if isinstance(msg.get('content'), list) and '_raw_image_data' in msg:
            # This is an image message that needs reformatting
            caption = next((item['text'] for item in msg['content'] if isinstance(item, dict) and item.get('type') == 'text'), '')
            
            if model == 'anthropic':
                formatted_content = [
                    {"type": "text", "text": caption},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": msg['_raw_image_data']
                        }
                    }
                ]
            else:  # openai and other models
                formatted_content = [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{msg['_raw_image_data']}"}}
                ]
            formatted_messages.append({"role": msg['role'], "content": formatted_content})
        else:
            # Regular text message
            if isinstance(msg.get('content'), list):
                # Convert list content to string if it's text only
                text_content = next((item['text'] for item in msg['content'] if isinstance(item, dict) and item.get('type') == 'text'), '')
                formatted_messages.append({"role": msg['role'], "content": text_content})
            else:
                formatted_messages.append(msg)
    
    return formatted_messages
