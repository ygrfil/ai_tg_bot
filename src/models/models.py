from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatPerplexity
from langchain_groq import ChatGroq
from config import ENV
from src.database.database import get_user_preferences
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def get_llm(selected_model: str, stream_handler, user_id: int):
    llm_config = {
        "openai": (ChatOpenAI, {"api_key": ENV["OPENAI_API_KEY"], "model": "gpt-4", "temperature": 0.4, "max_tokens": 1024}),
        "anthropic": (ChatAnthropic, {"api_key": ENV["ANTHROPIC_API_KEY"], "model": "claude-3-5-sonnet-20240620", "temperature": 0.4}),
        "perplexity": (ChatPerplexity, {"model": "llama-3.1-sonar-large-128k-online"}),
        "groq": (ChatGroq, {"model_name": "llama-3.1-70b-versatile", "temperature": 0.4}),
    }
    
    if selected_model not in llm_config:
        raise ValueError(f"Unknown model: {selected_model}")
    
    LLMClass, kwargs = llm_config[selected_model]
    try:
        return LLMClass(streaming=True, callbacks=[stream_handler], **kwargs)
    except Exception as e:
        raise ValueError(f"Error initializing {selected_model} model: {str(e)}")

def get_conversation_messages(user_conversation_history, user_id: int, selected_model: str):
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    messages = user_conversation_history.get(user_id, [])
    
    if not messages:
        return []
    
    if selected_model == "perplexity":
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        non_system_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        return system_messages + non_system_messages[-1:]
    
    processed_messages = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            processed_messages.append(msg)
        elif isinstance(msg, HumanMessage):
            if (selected_model == "anthropic" or selected_model == "openai") and isinstance(msg.content, list):
                # Keep the original format for Anthropic and OpenAI
                processed_messages.append(msg)
            else:
                # Convert to string for other models
                processed_messages.append(HumanMessage(content=str(msg.content)))
        elif isinstance(msg, AIMessage):
            processed_messages.append(AIMessage(content=str(msg.content)))
        elif isinstance(msg, str):
            processed_messages.append(HumanMessage(content=msg))
        else:
            processed_messages.append(HumanMessage(content=str(msg)))
    
    return processed_messages

def summarize_conversation(conversation_history, llm):
    summary_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant that summarizes conversations."),
        ("human", "Please summarize the following conversation:\n\n{conversation}")
    ])
    
    conversation_text = "\n".join([f"{msg.__class__.__name__}: {msg.content}" for msg in conversation_history])
    
    chain = summary_prompt | llm | StrOutputParser()
    summary = chain.invoke({"conversation": conversation_text})
    
    return summary
