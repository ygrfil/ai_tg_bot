import logging
from typing import List, Dict, Any, Union
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatPerplexity
from langchain_groq import ChatGroq
from config import ENV
from src.database.database import get_user_preferences
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

def get_llm(selected_model: str, stream_handler: Any, user_id: int) -> BaseChatModel:
    llm_config: Dict[str, tuple] = {
        "openai": (ChatOpenAI, {"api_key": ENV["OPENAI_API_KEY"], "model": "chatgpt-4o-latest", "temperature": 0.4, "max_tokens": 1024}),
        "anthropic": (ChatAnthropic, {"api_key": ENV["ANTHROPIC_API_KEY"], "model": "claude-3-5-sonnet-20240620", "temperature": 0.4}),
        "perplexity": (ChatPerplexity, {"model": "llama-3.1-sonar-large-128k-online"}),
        "groq": (ChatGroq, {"model_name": "llama-3.1-70b-versatile", "temperature": 0.4}),
    }
    
    if selected_model not in llm_config:
        logger.warning(f"Unknown model: {selected_model}. Defaulting to OpenAI.")
        selected_model = "openai"
    
    LLMClass, kwargs = llm_config[selected_model]
    try:
        llm = LLMClass(streaming=True, callbacks=[stream_handler], **kwargs)
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
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        non_system_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        return system_messages + non_system_messages[-1:]
    
    if selected_model == "anthropic":
        anthropic_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                anthropic_messages.append({"role": "user", "content": f"System: {msg.content}"})
            elif isinstance(msg, HumanMessage):
                anthropic_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                anthropic_messages.append({"role": "assistant", "content": msg.content})
        
        # Ensure the first message has the "user" role
        if anthropic_messages and anthropic_messages[0]["role"] != "user":
            anthropic_messages.insert(0, {"role": "user", "content": "Hello"})
        
        return anthropic_messages
    
    return [
        msg if isinstance(msg, (SystemMessage, AIMessage)) or
        (isinstance(msg, HumanMessage) and (selected_model in ["openai"]) and isinstance(msg.content, list))
        else HumanMessage(content=str(msg.content) if isinstance(msg, HumanMessage) else str(msg))
        for msg in messages
    ]
