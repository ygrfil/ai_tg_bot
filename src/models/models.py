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
    }
    
    if selected_model not in model_configs:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    api_key = ENV.get(f"{selected_model.upper()}_API_KEY")
    if not api_key:
        logger.warning(f"API key for {selected_model} is not set. Please check your environment variables.")
        return None
    
    client = model_configs[selected_model](api_key=api_key)
    return client.chat.completions.create if selected_model != "anthropic" else client.messages.create

def get_conversation_messages(user_conversation_history: Dict[int, List[Message]], user_id: int) -> List[Message]:
    messages = user_conversation_history[user_id]
    return messages[:-1] if messages and messages[-1]["role"] == "assistant" else messages
