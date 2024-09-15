import logging
from typing import List, Dict, Any, Union
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
from config import MODEL_CONFIG, ENV
from src.database.database import get_user_preferences
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

class SystemMessage(Message):
    def __init__(self, content: str):
        super().__init__("system", content)

class HumanMessage(Message):
    def __init__(self, content: str):
        super().__init__("user", content)

class AIMessage(Message):
    def __init__(self, content: str):
        super().__init__("assistant", content)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_llm(selected_model: str, stream_handler: Any, user_id: int):
    logger.info(f"Initializing LLM for model: {selected_model}")
    
    model_configs = {
        "openai": {
            "api_key": ENV.get("OPENAI_API_KEY"),
            "model": MODEL_CONFIG.get("openai_model"),
            "temperature": float(MODEL_CONFIG.get("openai_temperature", 0.7)),
            "max_tokens": int(MODEL_CONFIG.get("openai_max_tokens", 1024))
        },
        "anthropic": {
            "api_key": ENV.get("ANTHROPIC_API_KEY"),
            "model": MODEL_CONFIG.get("anthropic_model"),
            "temperature": float(MODEL_CONFIG.get("anthropic_temperature", 0.7)),
            "max_tokens_to_sample": int(MODEL_CONFIG.get("anthropic_max_tokens", 1024))
        },
        "perplexity": {
            "api_key": ENV.get("PERPLEXITY_API_KEY"),
            "model": MODEL_CONFIG.get("perplexity_model"),
            "base_url": "https://api.perplexity.ai"
        },
        "groq": {
            "api_key": ENV.get("GROQ_API_KEY"),
            "model": MODEL_CONFIG.get("groq_model"),
            "temperature": float(MODEL_CONFIG.get("groq_temperature", 0.7)),
            "max_tokens": int(MODEL_CONFIG.get("groq_max_tokens", 1024)),
            "base_url": MODEL_CONFIG.get("groq_base_url", "https://api.groq.com/openai/v1")
        },
        "hyperbolic": {
            "api_key": ENV.get("HYPERBOLIC_API_KEY"),
            "model": MODEL_CONFIG.get("hyperbolic_model"),
            "temperature": float(MODEL_CONFIG.get("hyperbolic_temperature", 0.7)),
            "max_tokens": int(MODEL_CONFIG.get("hyperbolic_max_tokens", 1024)),
            "base_url": MODEL_CONFIG.get("hyperbolic_base_url")
        },
        "gemini": {
            "api_key": ENV.get("GOOGLE_API_KEY"),
            "model": MODEL_CONFIG.get("gemini_model"),
            "temperature": float(MODEL_CONFIG.get("gemini_temperature", 0.7)),
            "max_output_tokens": int(MODEL_CONFIG.get("gemini_max_tokens", 1024)),
        },
    }
    
    if selected_model not in model_configs:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    config = model_configs[selected_model]
    
    if config.get("api_key") is None:
        error_message = f"API key for {selected_model} is not set. Please check your environment variables."
        logger.warning(error_message)
        return None
    
    try:
        if selected_model == "openai":
            client = OpenAI(api_key=config["api_key"])
            logger.info(f"OpenAI client initialized for user {user_id}")
            return client.chat.completions.create
        elif selected_model == "anthropic":
            client = Anthropic(api_key=config["api_key"])
            logger.info(f"Anthropic client initialized for user {user_id}")
            return lambda **kwargs: client.messages.create(**kwargs)
        elif selected_model == "gemini":
            genai.configure(api_key=config["api_key"])
            model = genai.GenerativeModel(config["model"])
            logger.info(f"Gemini model initialized for user {user_id}")
            return model.generate_content
        elif selected_model == "perplexity":
            client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
            logger.info(f"Perplexity client initialized for user {user_id}")
            return lambda **kwargs: client.chat.completions.create(**kwargs)
        else:
            # For other models, we'll use OpenAI's API with a different base URL
            client = OpenAI(api_key=config["api_key"], base_url=config.get("base_url", "https://api.openai.com/v1"))
            logger.info(f"{selected_model.capitalize()} client initialized for user {user_id}")
            return lambda **kwargs: client.chat.completions.create(**kwargs)
    except Exception as e:
        error_message = f"Error initializing {selected_model} model for user {user_id}: {str(e)}"
        logger.error(error_message)
        return None

def get_conversation_messages(user_conversation_history: Dict[int, List[Union[SystemMessage, HumanMessage, AIMessage]]], 
                              user_id: int, 
                              selected_model: str) -> List[Dict[str, str]]:
    messages = user_conversation_history.get(user_id, [])
    
    if not messages:
        return []
    
    if selected_model == "anthropic":
        return [
            {"role": "user" if msg.role == "user" else "assistant", "content": msg.content}
            for msg in messages if msg.role != "system"
        ]
    
    if selected_model == "gemini":
        return [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage))]
    
    # For OpenAI and other models
    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
