import logging
from typing import Dict, List, Callable
from telebot import TeleBot
from telebot.types import Message
from src.models.models import get_llm, get_conversation_messages
from src.database.database import (get_user_preferences, save_user_preferences, ensure_user_preferences,
                                   log_usage, get_monthly_usage, is_user_allowed,
                                   get_allowed_users, add_allowed_user, remove_allowed_user)
from src.utils.utils import (should_reset_conversation, create_keyboard, get_system_prompts,
                             get_username, StreamHandler, is_authorized,
                             remove_system_prompt, get_system_prompt)
from src.utils.decorators import authorized_only, admin_only
from config import ENV, load_model_config, MODEL_CONFIG

logger = logging.getLogger(__name__)

user_conversation_history: Dict[int, List[Dict[str, str]]] = {}

model_display_names = {
    'openai': 'ChatGPT (OpenAI)',
    'anthropic': 'Claude (Anthropic)', 
    'groq': 'Groq',
    'perplexity': 'Perplexity'
}

class CommandRouter:
    def __init__(self):
        self.handlers = {}

    def register(self, command: str, handler: Callable):
        self.handlers[command] = handler

    def handle(self, bot: TeleBot, message: Message):
        command = message.text.split()[0][1:]
        handler = self.handlers.get(command)
        if handler:
            handler(bot, message)
        else:
            bot.reply_to(message, f"Unknown command: {command}")

command_router = CommandRouter()

@authorized_only
def handle_commands(bot: TeleBot, message: Message) -> None:
    command_router.handle(bot, message)

def handle_model_selection(bot: TeleBot, message: Message) -> None:
    ensure_user_preferences(message.from_user.id)
    user_prefs = get_user_preferences(message.from_user.id)
    current_model = user_prefs.get('selected_model', 'openai')
    
    keyboard = create_keyboard([(display_name, f"model_{model}") for model, display_name in model_display_names.items()])
    bot.send_message(message.chat.id, f"Current model: {model_display_names.get(current_model, current_model)}\nSelect a model:", reply_markup=keyboard)

def handle_system_message_selection(bot: TeleBot, message: Message) -> None:
    ensure_user_preferences(message.from_user.id)
    bot.send_message(message.chat.id, "Select a system message:", reply_markup=create_keyboard([(name, f"sm_{name}") for name in get_system_prompts()]))

@admin_only
def handle_list_users(bot: TeleBot, message: Message) -> None:
    users = get_allowed_users()
    user_list = [f"ID: {user[0]}, Username: {get_username(bot, user[0])}" for user in users]
    bot.reply_to(message, "List of allowed users:\n" + "\n".join(user_list))

@admin_only
def handle_add_user(bot: TeleBot, message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "Usage: /add_user <user_id>")
        return
    
    user_id = int(parts[1])
    if add_allowed_user(user_id):
        username = get_username(bot, user_id)
        bot.reply_to(message, f"User {username} (ID: {user_id}) has been added to the allowed users list.")
    else:
        bot.reply_to(message, f"Failed to add user. The user might already be in the allowed list.")

@admin_only
def handle_remove_user(bot: TeleBot, message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "Usage: /remove_user <user_id>")
        return
    
    user_id = int(parts[1])
    if remove_allowed_user(user_id):
        bot.reply_to(message, f"User with ID {user_id} has been removed from the allowed users list.")
    else:
        bot.reply_to(message, f"Failed to remove user with ID {user_id}. Make sure the ID is correct.")

@admin_only
def handle_reload_config(bot: TeleBot, message: Message) -> None:
    MODEL_CONFIG.update(load_model_config('models_names.txt'))
    bot.reply_to(message, "Model configuration reloaded successfully.")

@admin_only
def handle_remove_prompt(bot: TeleBot, message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /remove_prompt <prompt_name>")
        return
    
    prompt_name = parts[1]
    if remove_system_prompt(prompt_name):
        bot.reply_to(message, f"System prompt '{prompt_name}' has been removed successfully.")
    else:
        bot.reply_to(message, f"Failed to remove system prompt '{prompt_name}'. Make sure the prompt name is correct.")

def handle_status(bot: TeleBot, message: Message) -> None:
    user_id = message.from_user.id
    ensure_user_preferences(user_id)
    user_prefs = get_user_preferences(user_id)
    usage = get_monthly_usage()
    user_usage = next((u for u in usage if u[0] == user_id), None)
    
    status_message = f"Your current status:\n\n" \
                     f"Current model: {user_prefs['selected_model']}\n" \
                     f"Current system prompt: {user_prefs['system_prompt']}\n\n" \
                     f"Monthly usage:\n" \
                     f"Total messages: {user_usage[2] if user_usage else 0}\n"
    
    bot.reply_to(message, status_message)

@admin_only
def handle_broadcast(bot: TeleBot, message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Please provide a message to broadcast after the /broadcast command.")
        return

    broadcast_message = parts[1]
    success_count = sum(send_broadcast(bot, int(user_id), broadcast_message) for user_id in ENV["ALLOWED_USER_IDS"])
    bot.reply_to(message, f"Broadcast sent successfully to {success_count} out of {len(ENV['ALLOWED_USER_IDS'])} allowed users.")

@admin_only
def handle_usage(bot: TeleBot, message: Message) -> None:
    usage_stats = get_monthly_usage()
    usage_report = "Monthly Usage Report (from the start of the current month):\n\n"
    for user_id, model, messages in usage_stats:
        username = get_username(bot, user_id)
        usage_report += f"User: {username}\n"
        usage_report += f"  Model: {model}\n"
        usage_report += f"    Messages: {messages}\n\n"
    bot.reply_to(message, usage_report)

def send_broadcast(bot: TeleBot, user_id: int, message: str) -> bool:
    try:
        bot.send_message(user_id, message)
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast to user {user_id}: {e}")
        return False

def callback_query_handler(bot: TeleBot, call):
    user_id = call.from_user.id
    ensure_user_preferences(user_id)
    if call.data.startswith('model_'):
        model_name = call.data.split('_')[1]
        save_user_preferences(user_id, selected_model=model_name)
        display_name = next((name for model, name in model_display_names.items() if model == model_name), model_name)
        bot.answer_callback_query(call.id, f"Switched to {display_name}")
        bot.edit_message_text(f"Model set to {display_name}", call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data.startswith('sm_'):
        prompt_name = call.data.split('_')[1]
        system_message = get_system_prompts().get(prompt_name, "You are a helpful assistant.")
        save_user_preferences(user_id, system_prompt=prompt_name)
        user_conversation_history[user_id] = [{"role": "system", "content": system_message}]
        bot.answer_callback_query(call.id, f"Switched to {prompt_name} system message. Conversation has been reset.")
        bot.edit_message_text(f"System message set to {prompt_name}. Conversation has been reset.", call.message.chat.id, call.message.message_id, reply_markup=None)

@authorized_only
def start_command(bot: TeleBot, message: Message) -> None:
    ensure_user_preferences(message.from_user.id)
    bot.reply_to(message, "Welcome! Here are the available commands:\n"
                          "/start: Introduces the bot and explains the available AI models.\n"
                          "/model: Select the AI model (OpenAI or Anthropic).\n"
                          "/sm: Select a system message to set the AI behavior and context.\n"
                          "/reset: Reset the conversation history.\n"
                          "/status: View your current status and usage.\n"
                          "Created by Yegor")

def startadmin_command(bot: TeleBot, message: Message) -> None:
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

def reset_command(bot: TeleBot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    user_conversation_history[message.from_user.id] = []
    bot.reply_to(message, "Conversation has been reset.")

def handle_message(bot: TeleBot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    user_id = message.from_user.id
    ensure_user_preferences(user_id)
    user_prefs = get_user_preferences(user_id)
    selected_model = user_prefs.get('selected_model', 'openai')

    if user_id not in user_conversation_history:
        user_conversation_history[user_id] = []

    if should_reset_conversation(user_id):
        user_conversation_history[user_id] = []
        bot.send_message(message.chat.id, "Your conversation has been reset due to inactivity.")

    placeholder_message = bot.send_message(message.chat.id, "Generating...")

    try:
        stream_handler = StreamHandler(bot, message.chat.id, placeholder_message.message_id)
        llm_function = get_llm(selected_model)
        
        if llm_function is None:
            bot.edit_message_text(
                f"The {selected_model} model is currently unavailable or not yet implemented. "
                "Please choose a different model using the /model command.\n"
                "Available models: OpenAI, Anthropic", 
                chat_id=message.chat.id, 
                message_id=placeholder_message.message_id
            )
            return

        logger.info(f"Using model: {selected_model}")

        if should_reset_conversation(user_id):
            system_prompt = get_system_prompt(user_id)
            user_conversation_history[user_id] = [{"role": "system", "content": system_prompt}]
            bot.send_message(message.chat.id, "Your conversation has been reset due to inactivity.")

        user_message = {"role": "user", "content": message.text}
        user_conversation_history[user_id].append(user_message)
        user_conversation_history[user_id] = user_conversation_history[user_id][-10:]
        messages = get_conversation_messages(user_conversation_history, user_id)
        
        model_name = MODEL_CONFIG.get(f"{selected_model}_model")
        max_tokens = int(MODEL_CONFIG.get(f"{selected_model}_max_tokens", 1024))
        temperature = float(MODEL_CONFIG.get(f"{selected_model}_temperature", 0.7))

        if selected_model == "anthropic":
            response = llm_function(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False
            )
            ai_response = response.choices[0].delta.content
            stream_handler.on_llm_end(ai_response)
        else:
            response = llm_function(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            ai_response = ""
            for chunk in response:
                if hasattr(chunk, 'choices') and chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    ai_response += content
                    stream_handler.on_llm_new_token(content)
            stream_handler.on_llm_end(ai_response)
        
        if not ai_response:
            raise ValueError("No response generated from the model.")
        
        user_conversation_history[user_id].append({"role": "assistant", "content": ai_response})
        user_conversation_history[user_id] = user_conversation_history[user_id][-10:]
        
        log_usage(user_id, selected_model, 1)
    except Exception as e:
        handle_message_error(bot, message, placeholder_message, e, user_id, selected_model)

# Register commands
command_router.register('model', handle_model_selection)
command_router.register('sm', handle_system_message_selection)
command_router.register('broadcast', handle_broadcast)
command_router.register('usage', handle_usage)
command_router.register('list_users', handle_list_users)
command_router.register('add_user', handle_add_user)
command_router.register('remove_user', handle_remove_user)
command_router.register('remove_prompt', handle_remove_prompt)
command_router.register('status', handle_status)
command_router.register('reload', handle_reload_config)

def handle_message_error(bot: TeleBot, message: Message, placeholder_message: Message, error: Exception, user_id: int, selected_model: str):
    error_message = str(error)
    logger.error(f"Error in handle_message: {error_message}", exc_info=True)

    if isinstance(error, ValueError) and "API key" in error_message:
        response = f"Configuration error: {error_message} Please contact the administrator or choose a different model using the /model command."
    elif 'rate_limit_exceeded' in error_message.lower():
        response = "The API rate limit has been exceeded. Please try again in a few moments or choose a different model using the /model command."
    elif 'invalid_request_error' in error_message.lower():
        logger.error(f"Invalid Request Error. User ID: {user_id}, Model: {selected_model}, Message: {message.content_type}")
        response = "There was an issue with the request. Please try again, choose a different model using the /model command, or contact support if the problem persists."
    elif 'context_length_exceeded' in error_message.lower():
        response = "The conversation is too long for the current model. Please use the /reset command to start a new conversation."
    else:
        response = f"An error occurred: {error_message}. Please try again or choose a different model using the /model command."

    bot.edit_message_text(response, chat_id=message.chat.id, message_id=placeholder_message.message_id)
