from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
import base64
import time
from config import ENV
from src.database.database import (get_user_preferences, save_user_preferences, ensure_user_preferences,
                      log_usage, get_monthly_usage)
from src.models.models import get_llm, get_conversation_messages
from src.utils.utils import (is_authorized, reset_conversation_if_needed, limit_conversation_history,
                   create_keyboard, get_system_prompts, get_username, StreamHandler)

user_conversation_history = {}

def handle_commands(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    command = message.text.split()[0][1:]
    if command == 'model':
        ensure_user_preferences(message.from_user.id)
        bot.send_message(message.chat.id, "Select a model:", reply_markup=create_keyboard([
            ("OpenAI", "model_openai"),
            ("Anthropic", "model_anthropic"),
            ("Perplexity", "model_perplexity"),
            ("Groq", "model_groq")
        ]))
    elif command == 'sm':
        ensure_user_preferences(message.from_user.id)
        bot.send_message(message.chat.id, "Select a system message:", reply_markup=create_keyboard([(name, f"sm_{name}") for name in get_system_prompts()]))
    elif command == 'broadcast':
        handle_broadcast(bot, message)
    elif command == 'usage':
        handle_usage(bot, message)

def handle_broadcast(bot, message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Please provide a message to broadcast after the /broadcast command.")
        return

    broadcast_message = parts[1]
    success_count = sum(send_broadcast(bot, int(user_id), broadcast_message) for user_id in ENV["ALLOWED_USER_IDS"])
    bot.reply_to(message, f"Broadcast sent successfully to {success_count} out of {len(ENV['ALLOWED_USER_IDS'])} allowed users.")

def handle_usage(bot, message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    usage_stats = get_monthly_usage()
    usage_report = "Monthly Usage Report (from the start of the current month):\n\n"
    for user_id, messages, tokens in usage_stats:
        username = get_username(bot, user_id)
        usage_report += f"User: {username}\n"
        usage_report += f"Total Messages: {messages}\n"
        usage_report += f"Estimated Tokens: {tokens}\n\n"
    bot.reply_to(message, usage_report)

def send_broadcast(bot, user_id: int, message: str) -> bool:
    try:
        bot.send_message(user_id, message)
        return True
    except Exception as e:
        print(f"Failed to send broadcast to user {user_id}: {e}")
        return False

def callback_query_handler(bot, call):
    user_id = call.from_user.id
    ensure_user_preferences(user_id)
    if call.data.startswith('model_'):
        model_name = call.data.split('_')[1]
        save_user_preferences(user_id, model_name)
        bot.answer_callback_query(call.id, f"Switched to {model_name} model.")
    else:
        prompt_name = call.data.split('_')[1]
        system_message = get_system_prompts().get(prompt_name, "You are a helpful assistant.")
        user_conversation_history[user_id] = [{"role": "system", "content": system_message}]
        bot.answer_callback_query(call.id, f"Switched to {prompt_name} system message.")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

def start_command(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    bot.reply_to(message, "Welcome! Here are the available commands:\n"
                          "/start: Introduces the bot and explains the available AI models.\n"
                          "/model: Select the AI model (OpenAI, Anthropic, Perplexity, or Groq).\n"
                          "/sm: Select a system message to set the AI behavior and context.\n"
                          "/reset: Reset the conversation history.\n"
                          "/summarize: Summarize the current conversation.\n"
                          "/broadcast: (Admin only) Send a message to all users.\n"
                          "/usage: (Admin only) View usage statistics.\n"
                          "Created by Yegor")

def reset_command(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    user_conversation_history[message.from_user.id] = []
    bot.reply_to(message, "Conversation has been reset.")

def summarize_command(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    user_id = message.from_user.id
    if user_id not in user_conversation_history or not user_conversation_history[user_id]:
        bot.reply_to(message, "There's no conversation to summarize.")
        return
    placeholder_message = bot.send_message(message.chat.id, "Generating summary...")
    summary = summarize_conversation(user_conversation_history[user_id])
    bot.edit_message_text(summary, chat_id=message.chat.id, message_id=placeholder_message.message_id)

def summarize_conversation(conversation_history):
    summary_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant that summarizes conversations."),
        ("human", "Summarize the following conversation concisely:\n{conversation}")
    ])
    llm = ChatAnthropic(api_key=ENV["ANTHROPIC_API_KEY"], model="claude-3-5-sonnet-20240620")
    chain = summary_prompt | llm | StrOutputParser()
    conversation_text = "\n".join(f"{type(msg).__name__}: {msg.content}" for msg in conversation_history)
    return chain.invoke({"conversation": conversation_text})

def create_prompt_command(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    bot.reply_to(message, "Please send the name for your new system prompt.")
    bot.register_next_step_handler(message, process_prompt_name)

def process_prompt_name(bot, message: Message) -> None:
    prompt_name = message.text.strip()
    if not prompt_name:
        bot.reply_to(message, "Invalid prompt name. Please try again with a valid name.")
        return
    bot.reply_to(message, f"Great! Now send the content for the '{prompt_name}' system prompt.")
    bot.register_next_step_handler(message, lambda m: process_prompt_content(bot, m, prompt_name))

def process_prompt_content(bot, message: Message, prompt_name: str) -> None:
    prompt_content = message.text.strip()
    if not prompt_content:
        bot.reply_to(message, "Invalid prompt content. Please try again with valid content.")
        return
    with open(f"system_prompts/{prompt_name}.txt", 'w') as file:
        file.write(prompt_content)
    bot.reply_to(message, f"System prompt '{prompt_name}' has been created and saved successfully!")

def handle_message(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    user_id = message.from_user.id
    ensure_user_preferences(user_id)
    user_prefs = get_user_preferences(user_id)
    selected_model = user_prefs['selected_model']

    reset_conversation_if_needed(user_id)

    user_message = process_message_content(message, bot)
    user_conversation_history.setdefault(user_id, []).append(user_message)
    limit_conversation_history(user_id)

    placeholder_message = bot.send_message(message.chat.id, "Generating...")

    try:
        stream_handler = StreamHandler(bot, message.chat.id, placeholder_message.message_id)
        llm = get_llm(selected_model, stream_handler)
        messages = get_conversation_messages(user_conversation_history, user_id, selected_model)
        
        response = llm.invoke(messages)
        
        user_conversation_history[user_id].append(AIMessage(content=stream_handler.response))
        
        messages_count = 1
        tokens_count = len(stream_handler.response.split())
        log_usage(user_id, selected_model, messages_count, tokens_count)
    except Exception as e:
        bot.edit_message_text(f"An error occurred: {str(e)}", chat_id=message.chat.id, message_id=placeholder_message.message_id)

def process_message_content(message: Message, bot) -> HumanMessage:
    if message.content_type == 'photo':
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image_url = f"data:image/jpeg;base64,{base64.b64encode(downloaded_file).decode('utf-8')}"
        return HumanMessage(content=[
            {"type": "text", "text": message.caption or "Analyze this image."},
            {"type": "image_url", "image_url": {"url": image_url}}
        ])
    return HumanMessage(content=message.text)