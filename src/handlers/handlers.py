import logging
from typing import Dict, List

logger = logging.getLogger(__name__)
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
import base64
import os
from config import ENV, load_model_config, MODEL_CONFIG
from src.database.database import (get_user_preferences, save_user_preferences, ensure_user_preferences,
                      log_usage, get_monthly_usage, get_user_monthly_usage)
from src.models.models import get_llm, get_conversation_messages
from src.utils.utils import (reset_conversation_if_needed,
                   create_keyboard, get_system_prompts, get_username, get_user_id, StreamHandler, is_authorized,
                   remove_system_prompt, get_system_prompt)
from src.database.database import is_user_allowed, get_allowed_users, add_allowed_user, remove_allowed_user

user_conversation_history: Dict[int, List[HumanMessage | AIMessage | SystemMessage]] = {}

import requests
from typing import Dict, Callable
from telebot import TeleBot
import time

from src.utils.decorators import authorized_only

@authorized_only
def handle_commands(bot: TeleBot, message: Message) -> None:

    command = message.text.split()[0][1:]
    command_handlers: Dict[str, Callable[[], None]] = {
        'model': lambda: handle_model_selection(bot, message),
        'sm': lambda: handle_system_message_selection(bot, message),
        'broadcast': lambda: handle_broadcast(bot, message),
        'usage': lambda: handle_usage(bot, message),
        'create_prompt': lambda: create_prompt_command(bot, message),
        'list_users': lambda: handle_list_users(bot, message),
        'add_user': lambda: handle_add_user(bot, message),
        'remove_user': lambda: handle_remove_user(bot, message),
        'remove_prompt': lambda: handle_remove_prompt(bot, message),
        'status': lambda: handle_status(bot, message),
        'btc': lambda: handle_btc_price(bot, message),
        'reload': lambda: handle_reload_config(bot, message)
    }

    handler = command_handlers.get(command)
    if handler:
        handler()
    else:
        bot.reply_to(message, f"Unknown command: {command}")

def handle_model_selection(bot, message: Message) -> None:
    ensure_user_preferences(message.from_user.id)
    user_prefs = get_user_preferences(message.from_user.id)
    current_model = user_prefs.get('selected_model', 'openai')  # Default to 'openai' if not set
    model_display_names = {key.split('_')[0]: value for key, value in MODEL_CONFIG.items() if key.endswith('_model')}
    bot.send_message(message.chat.id, f"Current model: {model_display_names.get(current_model, current_model)}\nSelect a model:", reply_markup=create_keyboard([
        (model_display_names["openai"], "model_openai"),
        (model_display_names["anthropic"], "model_anthropic"),
        (model_display_names["perplexity"], "model_perplexity"),
        (model_display_names["groq"], "model_groq"),
        (model_display_names["hyperbolic"], "model_hyperbolic"),
        (model_display_names["gemini"], "model_gemini")
    ]))

def handle_system_message_selection(bot, message: Message) -> None:
    ensure_user_preferences(message.from_user.id)
    bot.send_message(message.chat.id, "Select a system message:", reply_markup=create_keyboard([(name, f"sm_{name}") for name in get_system_prompts()]))

from src.utils.decorators import authorized_only, admin_only

@admin_only
def handle_list_users(bot, message: Message) -> None:
    users = get_allowed_users()
    user_list = []
    for user in users:
        username = get_username(bot, user[0])
        user_list.append(f"ID: {user[0]}, Username: {username}")
    
    user_list_str = "\n".join(user_list)
    bot.reply_to(message, f"List of allowed users:\n{user_list_str}")

@admin_only
def handle_add_user(bot, message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /add_user <user_id>")
        return
    
    user_id = parts[1]
    if not user_id.isdigit():
        bot.reply_to(message, "Invalid user ID. Please provide a numeric ID.")
        return
    
    user_id = int(user_id)
    result = add_allowed_user(user_id)
    if result:
        username = get_username(bot, user_id)
        bot.reply_to(message, f"User {username} (ID: {user_id}) has been added to the allowed users list.")
    else:
        bot.reply_to(message, f"Failed to add user. The user might already be in the allowed list.")

@admin_only
def handle_remove_user(bot, message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /remove_user <user_id>")
        return
    
    user_id = parts[1]
    if not user_id.isdigit():
        bot.reply_to(message, "Invalid user ID. Please provide a numeric ID.")
        return
    
    user_id = int(user_id)
    result = remove_allowed_user(user_id)
    if result:
        bot.reply_to(message, f"User with ID {user_id} has been removed from the allowed users list.")
    else:
        bot.reply_to(message, f"Failed to remove user with ID {user_id}. Make sure the ID is correct.")

@admin_only
def handle_reload_config(bot, message: Message) -> None:
    from config import MODEL_CONFIG
    MODEL_CONFIG.update(load_model_config('models_names.txt'))
    bot.reply_to(message, "Model configuration reloaded successfully.")
@admin_only
def handle_remove_prompt(bot, message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /remove_prompt <prompt_name>")
        return
    
    prompt_name = parts[1]
    result = remove_system_prompt(prompt_name)
    if result:
        bot.reply_to(message, f"System prompt '{prompt_name}' has been removed successfully.")
    else:
        bot.reply_to(message, f"Failed to remove system prompt '{prompt_name}'. Make sure the prompt name is correct.")

def handle_status(bot, message: Message) -> None:
    user_id = message.from_user.id
    ensure_user_preferences(user_id)
    user_prefs = get_user_preferences(user_id)
    usage = get_user_monthly_usage(user_id)
    
    status_message = f"Your current status:\n\n"
    status_message += f"Current model: {user_prefs['selected_model']}\n"
    status_message += f"Current system prompt: {user_prefs['system_prompt']}\n\n"
    status_message += f"Monthly usage:\n"
    status_message += f"Total messages: {usage[0] if usage else 0}\n"
    
    bot.reply_to(message, status_message)

from datetime import datetime

@authorized_only
def handle_btc_price(bot: TeleBot, message: Message) -> None:

    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price', params={'ids': 'bitcoin', 'vs_currencies': 'usd'}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'bitcoin' in data and 'usd' in data['bitcoin']:
            price = data['bitcoin']['usd']
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bot.reply_to(message, f"Current time: {current_time}\nThe current BTC/USD price is: ${price:,.2f}")
        else:
            bot.reply_to(message, "Unable to fetch the current BTC price. Please try again later.")
    except Exception as e:
        logger.error(f"Error fetching BTC price: {str(e)}")
        bot.reply_to(message, "An error occurred while fetching the BTC price. Please try again later.")

@admin_only
def handle_broadcast(bot, message: Message) -> None:

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Please provide a message to broadcast after the /broadcast command.")
        return

    broadcast_message = parts[1]
    success_count = sum(send_broadcast(bot, int(user_id), broadcast_message) for user_id in ENV["ALLOWED_USER_IDS"])
    bot.reply_to(message, f"Broadcast sent successfully to {success_count} out of {len(ENV['ALLOWED_USER_IDS'])} allowed users.")

@admin_only
def handle_usage(bot, message: Message) -> None:
    usage_stats = get_monthly_usage()
    usage_report = "Monthly Usage Report (from the start of the current month):\n\n"
    current_user = None
    for user_id, model, messages in usage_stats:
        if current_user != user_id:
            if current_user is not None:
                usage_report += "\n"
            username = get_username(bot, user_id)
            usage_report += f"User: {username}\n"
            current_user = user_id
        usage_report += f"  Model: {model}\n"
        usage_report += f"    Messages: {messages}\n"
    bot.reply_to(message, usage_report)

def send_broadcast(bot, user_id: int, message: str) -> bool:
    try:
        bot.send_message(user_id, message)
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast to user {user_id}: {e}")
        return False

def callback_query_handler(bot, call):
    user_id = call.from_user.id
    ensure_user_preferences(user_id)
    if call.data.startswith('model_'):
        model_name = call.data.split('_')[1]
        save_user_preferences(user_id, selected_model=model_name)
        bot.answer_callback_query(call.id, f"Switched to {model_name} model.")
        bot.edit_message_text(f"Model set to {model_name}.", call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data.startswith('sm_'):
        prompt_name = call.data.split('_')[1]
        system_message = get_system_prompts().get(prompt_name, "You are a helpful assistant.")
        save_user_preferences(user_id, system_prompt=prompt_name)
        user_conversation_history[user_id] = [SystemMessage(content=system_message)]
        bot.answer_callback_query(call.id, f"Switched to {prompt_name} system message. Conversation has been reset.")
        bot.edit_message_text(f"System message set to {prompt_name}. Conversation has been reset.", call.message.chat.id, call.message.message_id, reply_markup=None)

@authorized_only
def start_command(bot, message: Message) -> None:
    ensure_user_preferences(message.from_user.id)
    bot.reply_to(message, "Welcome! Here are the available commands:\n"
                          "/start: Introduces the bot and explains the available AI models.\n"
                          "/model: Select the AI model (OpenAI, Anthropic, Perplexity, or Groq).\n"
                          "/sm: Select a system message to set the AI behavior and context.\n"
                          "/reset: Reset the conversation history.\n"
                          "/create_prompt: Create a new system prompt.\n"
                          "/status: View your current status and usage.\n"
                          "Created by Yegor")

def startadmin_command(bot, message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    bot.reply_to(message, "Welcome, Admin! Here are the available admin commands:\n"
                          "/startadmin: Shows all admin commands.\n"
                          "/broadcast: Send a message to all users.\n"
                          "/usage: View usage statistics.\n"
                          "/list_users: List all allowed users.\n"
                          "/add_user: Add a new allowed user.\n"
                          "/remove_user: Remove an allowed user.\n"
                          "/remove_prompt: Remove a system prompt.")

def reset_command(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    user_conversation_history[message.from_user.id] = []
    bot.reply_to(message, "Conversation has been reset.")

def create_prompt_command(bot: TeleBot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    bot.reply_to(message, "Please send the name for your new system prompt.")
    bot.register_next_step_handler(message, lambda m: process_prompt_name(bot, m))

def process_prompt_name(bot: TeleBot, message: Message) -> None:
    prompt_name = message.text.strip()
    if not prompt_name or '/' in prompt_name:
        bot.reply_to(message, "Invalid prompt name. Please try again with a valid name without '/'.")
        return
    bot.reply_to(message, f"Great! Now send the content for the '{prompt_name}' system prompt.")
    bot.register_next_step_handler(message, lambda m: process_prompt_content(bot, m, prompt_name))

def process_prompt_content(bot, message: Message, prompt_name: str) -> None:
    prompt_content = message.text.strip()
    if not prompt_content:
        bot.reply_to(message, "Invalid prompt content. Please try again with valid content.")
        return
    
    prompt_dir = "system_prompts"
    os.makedirs(prompt_dir, exist_ok=True)
    
    with open(os.path.join(prompt_dir, f"{prompt_name}.txt"), 'w') as file:
        file.write(prompt_content)
    bot.reply_to(message, f"System prompt '{prompt_name}' has been created and saved successfully!")

def handle_message(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    user_id = message.from_user.id
    ensure_user_preferences(user_id)
    user_prefs = get_user_preferences(user_id)
    selected_model = user_prefs.get('selected_model', 'anthropic')  # Default to 'anthropic' if not set

    if user_id not in user_conversation_history:
        user_conversation_history[user_id] = []

    # Check if the conversation needs to be reset due to inactivity
    if reset_conversation_if_needed(user_id):
        user_conversation_history[user_id] = []
        bot.send_message(message.chat.id, "Your conversation has been reset due to inactivity.")

    # Check if the message contains an image and the selected model is not OpenAI or Anthropic
    if message.content_type == 'photo' and selected_model not in ['openai', 'anthropic']:
        bot.reply_to(message, "Image processing is only available with OpenAI or Anthropic models. Please change your model using the /model command.")
        return

    placeholder_message = bot.send_message(message.chat.id, "Generating...")

    try:
        stream_handler = StreamHandler(bot, message.chat.id, placeholder_message.message_id)
        llm = get_llm(selected_model, stream_handler, user_id)
        
        if reset_conversation_if_needed(user_id):
            system_prompt = get_system_prompt(user_id)
            user_conversation_history[user_id] = [SystemMessage(content=system_prompt)]
            bot.send_message(message.chat.id, "Your conversation has been reset due to inactivity.")

        user_message = process_message_content(message, bot, selected_model)
        user_conversation_history[user_id].append(user_message)
        user_conversation_history[user_id] = user_conversation_history[user_id][-10:]  # Keep only the last 10 messages
        messages = get_conversation_messages(user_conversation_history, user_id, selected_model)
        response = llm.invoke(messages)
        
        user_conversation_history[user_id].append(AIMessage(content=stream_handler.response))
        user_conversation_history[user_id] = user_conversation_history[user_id][-10:]  # Ensure we still have only 10 messages after adding the response
        
        messages_count = 1
        log_usage(user_id, selected_model, messages_count)
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error in handle_message: {error_message}")
        if 'overloaded_error' in error_message.lower():
            bot.edit_message_text("The AI model is currently overloaded. Please try again in a few moments.", chat_id=message.chat.id, message_id=placeholder_message.message_id)
        elif '400 bad request' in error_message.lower():
            logger.error(f"Bad Request Error. User ID: {user_id}, Model: {selected_model}, Message: {message.content_type}")
            bot.edit_message_text("There was an issue with the request. Please try again or contact support if the problem persists.", chat_id=message.chat.id, message_id=placeholder_message.message_id)
        else:
            bot.edit_message_text(f"An error occurred: {error_message}", chat_id=message.chat.id, message_id=placeholder_message.message_id)

from src.utils.image_utils import process_image_message

def process_message_content(message: Message, bot, selected_model: str) -> HumanMessage:
    if message.content_type == 'photo':
        image_content = process_image_message(message, bot, selected_model)
        text_content = {"type": "text", "text": message.caption or "Describe the image in detail"}
        return HumanMessage(content=[image_content, text_content])
    return HumanMessage(content=message.text or "Please provide a message or an image.")
