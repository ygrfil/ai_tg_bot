from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatPerplexity
from langchain_groq import ChatGroq
from config import ENV
from src.database.database import get_user_preferences
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

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
def summarize_conversation_history(conversation_history):
    summarizer = ChatAnthropic(model="claude-3-haiku-20240307", temperature=0.2)
    summary_prompt = "Summarize the following conversation concisely, preserving key information:\n\n"
    for message in conversation_history:
        if isinstance(message, SystemMessage):
            summary_prompt += f"System: {message.content}\n"
        elif isinstance(message, HumanMessage):
            summary_prompt += f"Human: {message.content}\n"
        elif isinstance(message, AIMessage):
            summary_prompt += f"AI: {message.content}\n"
    
    summary = summarizer.invoke(summary_prompt)
    return [HumanMessage(content=summary.content)]
