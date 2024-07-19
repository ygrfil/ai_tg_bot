from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatPerplexity
from langchain_groq import ChatGroq
from config import ENV
from src.database.database import get_user_preferences
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def summarize_conversation(conversation_history):
    summary_prompt = ChatPromptTemplate.from_messages([
        ("system", "You make all conversation much shorter, summarize keeping style and most important points the same"),
        ("human", "Summarize the following conversation concisely:\n{conversation}")
    ])
    llm = ChatAnthropic(api_key=ENV["ANTHROPIC_API_KEY"], model="claude-3-5-sonnet-20240620")
    chain = summary_prompt | llm | StrOutputParser()
    conversation_text = "\n".join(f"{type(msg).__name__}: {msg['content'] if isinstance(msg, dict) else msg.content}" for msg in conversation_history)
    return chain.invoke({"conversation": conversation_text})

def get_llm(selected_model: str, stream_handler, user_id: int):
    llm_config = {
        "openai": (ChatOpenAI, {"api_key": ENV["OPENAI_API_KEY"], "model": "gpt-4o", "temperature": 0.2}),
        "anthropic": (ChatAnthropic, {"api_key": ENV["ANTHROPIC_API_KEY"], "model": "claude-3-5-sonnet-20240620", "temperature": 0.2}),
        "perplexity": (ChatPerplexity, {"model": "llama-3-sonar-large-32k-online"}),
        "groq": (ChatGroq, {"model_name": "llama3-70b-8192", "temperature": 0.2}),
    }
    
    if selected_model not in llm_config:
        raise ValueError(f"Unknown model: {selected_model}")
    
    LLMClass, kwargs = llm_config[selected_model]
    return LLMClass(streaming=True, callbacks=[stream_handler], **kwargs)

def get_conversation_messages(user_conversation_history, user_id: int, selected_model: str):
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    messages = user_conversation_history[user_id]
    
    if selected_model == "perplexity":
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        non_system_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        return system_messages + non_system_messages[-1:]
    
    if selected_model in ["anthropic", "groq"]:
        first_non_system = next((i for i, msg in enumerate(messages) if not isinstance(msg, SystemMessage)), None)
        if first_non_system is not None and not isinstance(messages[first_non_system], HumanMessage):
            messages[first_non_system] = HumanMessage(content=messages[first_non_system].content)
    
    # Ensure all message contents are strings for Groq and Anthropic
    if selected_model in ["groq", "anthropic"]:
        messages = [
            msg.__class__(content=str(msg.content) if isinstance(msg.content, (list, dict)) else msg.content)
            for msg in messages
        ]
    
    return messages
