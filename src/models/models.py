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
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class LLMConfig(BaseModel):
    api_key: str = Field(..., description="API key for the model")
    model: str = Field(..., description="Model name")
    temperature: float = Field(0.7, description="Temperature for text generation")
    max_tokens: int = Field(1024, description="Maximum number of tokens to generate")

def get_llm(selected_model: str, stream_handler: Any, user_id: int) -> BaseChatModel:
    llm_config: Dict[str, tuple] = {
        "openai": (ChatOpenAI, LLMConfig(api_key=ENV.get("OPENAI_API_KEY"), model=MODEL_CONFIG.get("openai_model"), temperature=float(MODEL_CONFIG.get("openai_temperature")))),
        "anthropic": (ChatAnthropic, LLMConfig(api_key=ENV.get("ANTHROPIC_API_KEY"), model=MODEL_CONFIG.get("anthropic_model"), temperature=float(MODEL_CONFIG.get("anthropic_temperature")))),
        "perplexity": (ChatPerplexity, LLMConfig(api_key=ENV.get("PERPLEXITY_API_KEY"), model=MODEL_CONFIG.get("perplexity_model"))),
        "groq": (ChatGroq, LLMConfig(api_key=ENV.get("GROQ_API_KEY"), model=MODEL_CONFIG.get("groq_model"), temperature=float(MODEL_CONFIG.get("groq_temperature")))),
        "hyperbolic": (ChatOpenAI, LLMConfig(api_key=ENV.get("HYPERBOLIC_API_KEY"), model=MODEL_CONFIG.get("hyperbolic_model"), temperature=float(MODEL_CONFIG.get("hyperbolic_temperature")))),
        "gemini": (ChatGoogleGenerativeAI, LLMConfig(api_key=ENV.get("GOOGLE_API_KEY"), model=MODEL_CONFIG.get("gemini_model"), temperature=float(MODEL_CONFIG.get("gemini_temperature")))),
    }
    
    if selected_model not in llm_config:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    LLMClass, config = llm_config[selected_model]
    try:
        llm = LLMClass(streaming=True, callbacks=[stream_handler], **config.dict())
        return llm
    except Exception as e:
        logger.error(f"Error initializing {selected_model} model for user {user_id}: {str(e)}")
        raise ValueError(f"Error initializing {selected_model} model: {str(e)}")

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
