import logging
from typing import List, Dict, Any, Union
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatPerplexity
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from config import MODEL_CONFIG, ENV
from src.database.database import get_user_preferences
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

def get_llm(selected_model: str, stream_handler: Any, user_id: int) -> BaseChatModel:
    logger.info(f"Initializing LLM for model: {selected_model}")
    llm_config = {
        "openai": (ChatOpenAI, {
            "api_key": ENV.get("OPENAI_API_KEY"),
            "model": MODEL_CONFIG.get("openai_model"),
            "temperature": float(MODEL_CONFIG.get("openai_temperature", 0.7)),
            "max_tokens": int(MODEL_CONFIG.get("openai_max_tokens", 1024))
        }),
        "anthropic": (ChatAnthropic, {
            "api_key": ENV.get("ANTHROPIC_API_KEY"),
            "model": MODEL_CONFIG.get("anthropic_model"),
            "temperature": float(MODEL_CONFIG.get("anthropic_temperature", 0.7)),
            "max_tokens": int(MODEL_CONFIG.get("anthropic_max_tokens", 1024))
        }),
        "perplexity": (ChatPerplexity, {
            "api_key": ENV.get("PERPLEXITY_API_KEY"),
            "model": MODEL_CONFIG.get("perplexity_model")
        }),
        "groq": (ChatGroq, {
            "api_key": ENV.get("GROQ_API_KEY"),
            "model": MODEL_CONFIG.get("groq_model"),
            "temperature": float(MODEL_CONFIG.get("groq_temperature", 0.7)),
            "max_tokens": int(MODEL_CONFIG.get("groq_max_tokens", 1024))
        }),
        "hyperbolic": (ChatOpenAI, {
            "api_key": ENV.get("HYPERBOLIC_API_KEY"),
            "model": MODEL_CONFIG.get("hyperbolic_model"),
            "temperature": float(MODEL_CONFIG.get("hyperbolic_temperature", 0.7)),
            "max_tokens": int(MODEL_CONFIG.get("hyperbolic_max_tokens", 1024))
        }),
        "gemini": (ChatGoogleGenerativeAI, {
            "api_key": ENV.get("GOOGLE_API_KEY"),
            "model": MODEL_CONFIG.get("gemini_model"),
            "temperature": float(MODEL_CONFIG.get("gemini_temperature", 0.7)),
            "max_output_tokens": int(MODEL_CONFIG.get("gemini_max_tokens", 1024))
        }),
    }
    
    logger.info(f"Model config for {selected_model}: {llm_config[selected_model]}")
    
    if selected_model not in llm_config:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    LLMClass, config = llm_config[selected_model]
    
    if config["api_key"] is None:
        if selected_model == "gemini":
            logger.warning(f"API key for {selected_model} is not set. Skipping this model.")
            return None
        else:
            error_message = f"API key for {selected_model} is not set. Please check your environment variables."
            logger.error(error_message)
            raise ValueError(error_message)
    
    try:
        llm = LLMClass(streaming=True, callbacks=[stream_handler], **config)
        return llm
    except Exception as e:
        error_message = f"Error initializing {selected_model} model for user {user_id}: {str(e)}"
        logger.error(error_message)
        raise ValueError(error_message)

def get_conversation_messages(user_conversation_history: Dict[int, List[Union[SystemMessage, HumanMessage, AIMessage]]], 
                              user_id: int, 
                              selected_model: str) -> List[Union[SystemMessage, HumanMessage, AIMessage]]:
    messages = user_conversation_history.get(user_id, [])
    
    if not messages:
        return []
    
    if selected_model == "perplexity":
        return [msg for msg in messages if isinstance(msg, SystemMessage)] + messages[-1:]
    
    if selected_model == "anthropic":
        return [
            {"role": "user" if isinstance(msg, (SystemMessage, HumanMessage)) else "assistant", 
             "content": f"System: {msg.content}" if isinstance(msg, SystemMessage) else msg.content}
            for msg in messages
        ]
    
    return [
        msg if isinstance(msg, (SystemMessage, AIMessage)) or
        (isinstance(msg, HumanMessage) and selected_model == "openai" and isinstance(msg.content, list))
        else HumanMessage(content=str(msg.content))
        for msg in messages
    ]
