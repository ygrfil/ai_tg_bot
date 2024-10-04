import logging
from typing import List, Dict, Any, Union
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
from config import MODEL_CONFIG, ENV
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

Message = Dict[str, str]

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_llm(selected_model: str, stream_handler: Any, user_id: int):
    logger.info(f"Initializing LLM for model: {selected_model}")
    
    model_configs = {
        "openai": OpenAI,
        "anthropic": Anthropic,
        "perplexity": lambda **kwargs: OpenAI(base_url="https://api.perplexity.ai", **kwargs),
        "groq": lambda **kwargs: OpenAI(base_url=MODEL_CONFIG.get("groq_base_url", "https://api.groq.com/openai/v1"), **kwargs),
        "hyperbolic": lambda **kwargs: OpenAI(base_url=MODEL_CONFIG.get("hyperbolic_base_url"), **kwargs),
        "gemini": genai.GenerativeModel,
        "o1": lambda **kwargs: OpenAI(base_url="https://api.openai.com/v1", **kwargs),
    }
    
    if selected_model not in model_configs:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    if selected_model == "gemini":
        api_key = ENV.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("API key for Gemini is not set. Please check your environment variables.")
            return None
        genai.configure(api_key=api_key)
        model = model_configs[selected_model](MODEL_CONFIG.get(f"{selected_model}_model"))
        return lambda messages: model.generate_content(messages).text
    else:
        api_key = ENV.get(f"{selected_model.upper()}_API_KEY")
        if not api_key:
            logger.warning(f"API key for {selected_model} is not set. Please check your environment variables.")
            return None
        client = model_configs[selected_model](api_key=api_key)
        return client.chat.completions.create if selected_model not in ["anthropic", "o1"] else client.messages.create

def get_conversation_messages(user_conversation_history: Dict[int, List[Message]], user_id: int, selected_model: str) -> Union[str, List[Message]]:
    messages = user_conversation_history[user_id]
    
    if selected_model == "gemini":
        user_messages = [msg["content"] for msg in messages if msg["role"] == "user"]
        return user_messages[-1] if user_messages else ""
    
    return messages[:-1] if messages and messages[-1]["role"] == "assistant" else messages
