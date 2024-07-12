from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatPerplexity
from langchain_groq import ChatGroq
from config import ENV

def get_llm(selected_model: str, stream_handler):
    llm_config = {
        "openai": (ChatOpenAI, {"api_key": ENV["OPENAI_API_KEY"], "model": "gpt-4o"}),
        "anthropic": (ChatAnthropic, {"api_key": ENV["ANTHROPIC_API_KEY"], "model": "claude-3-5-sonnet-20240620"}),
        "perplexity": (ChatPerplexity, {"model": "llama-3-sonar-large-32k-online"}),
        "groq": (ChatGroq, {"model_name": "llama3-70b-8192"}),
    }
    
    if selected_model not in llm_config:
        raise ValueError(f"Unknown model: {selected_model}")
    
    LLMClass, kwargs = llm_config[selected_model]
    return LLMClass(streaming=True, callbacks=[stream_handler], **kwargs)

def get_conversation_messages(user_conversation_history, user_id: int, selected_model: str):
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    if selected_model == "perplexity":
        messages = [msg for msg in user_conversation_history[user_id] if isinstance(msg, SystemMessage)]
        human_messages = [msg for msg in user_conversation_history[user_id] if isinstance(msg, HumanMessage)]
        if human_messages:
            messages.append(human_messages[-1])
        return messages
    
    messages = [msg if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)) else SystemMessage(content=msg['content']) for msg in user_conversation_history[user_id]]
    
    if selected_model == "anthropic":
        first_non_system = next((i for i, msg in enumerate(messages) if not isinstance(msg, SystemMessage)), None)
        if first_non_system is not None and not isinstance(messages[first_non_system], HumanMessage):
            messages[first_non_system] = HumanMessage(content=messages[first_non_system].content)
    
    return messages
