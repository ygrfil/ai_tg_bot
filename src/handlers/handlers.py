import logging
from typing import Dict, List, Callable
from telebot import TeleBot
from telebot.types import Message
from src.models.models import get_llm, get_conversation_messages, format_messages_for_model
from src.database.database import (get_user_preferences, save_user_preferences, ensure_user_preferences,
                                   log_usage, get_monthly_usage, is_user_allowed,
                                   get_allowed_users, add_allowed_user, remove_allowed_user)
from src.utils.utils import (should_reset_conversation, create_keyboard, get_system_prompts,
                             get_username, StreamHandler, is_authorized,
                             remove_system_prompt, get_system_prompt, process_image_message)
from src.utils.decorators import authorized_only, admin_only
from config import ENV, load_model_config, MODEL_CONFIG

logger = logging.getLogger(__name__)

user_conversation_history: Dict[int, List[Dict[str, str]]] = {}

model_display_names = {
    'openai': 'ChatGPT (OpenAI)',
    'anthropic': 'Claude (Anthropic)', 
    'groq': 'Groq',
    'perplexity': 'Perplexity AI'
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
        
        # Check if current conversation has images and switching to non-supported model
        if user_id in user_conversation_history:
            has_images = any(
                isinstance(msg.get('content'), list) and '_raw_image_data' in msg 
                for msg in user_conversation_history[user_id]
            )
            if has_images and model_name not in ['anthropic', 'openai']:
                user_conversation_history[user_id] = []
                bot.answer_callback_query(call.id, "Conversation reset: images are only supported with Claude and ChatGPT")
                
        save_user_preferences(user_id, selected_model=model_name)
        display_name = next((name for model, name in model_display_names.items() if model == model_name), model_name)
        bot.answer_callback_query(call.id, f"Switched to {display_name}")
        
        message_text = f"Model set to {display_name}"
        if model_name not in ['anthropic', 'openai']:
            message_text += "\nNote: This model doesn't support image analysis"
            
        bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id, reply_markup=None)
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

        if message.content_type == 'photo':
            if selected_model not in ['anthropic', 'openai']:
                bot.reply_to(message, "Image analysis is only supported with Claude (Anthropic) and ChatGPT (OpenAI) models. Please switch to one of these models.")
                return
                
            image_data = process_image_message(message, bot, selected_model)
            caption = message.caption or "Please analyze this image."
            
            if selected_model == "anthropic":
                user_message = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        image_data
                    ]
                }
            else:  # openai and other models
                user_message = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data['source']['data']}"}}
                    ]
                }
            # Store the raw image data for potential model switching
            user_message['_raw_image_data'] = image_data['source']['data']
        else:
            user_message = {"role": "user", "content": message.text}
        user_conversation_history[user_id].append(user_message)
        user_conversation_history[user_id] = user_conversation_history[user_id][-10:]
        messages = format_messages_for_model(get_conversation_messages(user_conversation_history, user_id), selected_model)
        
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
            if hasattr(response.choices[0], 'delta'):
                ai_response = response.choices[0].delta.content
            else:
                ai_response = response.content[0].text
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
command_router.register('btc', lambda bot, message: handle_btc_price(bot, message))

def handle_btc_price(bot: TeleBot, message: Message) -> None:
    """Handle /btc command to show current BTC price"""
    try:
        timestamp, price = get_btc_price()
        bot.reply_to(message, f"🕒 {timestamp}\n💰 BTC/USD: ${price:,.2f}")
    except Exception as e:
        bot.reply_to(message, f"Error fetching BTC price: {str(e)}")

def get_btc_price() -> tuple[str, float]:
    """Fetch current BTC/USD price from CoinGecko API"""
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd')
        response.raise_for_status()
        price = response.json()['bitcoin']['usd']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return current_time, price
    except Exception as e:
        logger.error(f"Error fetching BTC price: {e}")
        raise RuntimeError("Failed to fetch BTC price")

def handle_message_error(bot: TeleBot, message: Message, placeholder_message: Message, error: Exception, user_id: int, selected_model: str):
    error_message = str(error).lower()
    logger.error(f"Error in handle_message: {error_message}", exc_info=True)

    error_responses = {
        'api key': "Configuration error. Please contact the administrator.",
        'rate_limit_exceeded': "Rate limit exceeded. Please try again in a few moments.",
        'invalid_request_error': "Invalid request. Please try again or switch models.",
        'context_length_exceeded': "Conversation too long. Please use /reset command.",
        'content_policy_violation': "Content policy violation. Please try with different content.",
        'invalid_api_key': "API key configuration error. Please contact the administrator.",
    }

    response = next((msg for key, msg in error_responses.items() if key in error_message), 
                   f"Error: {str(error)}. Please try again or use /model command.")

    try:
        bot.edit_message_text(response, chat_id=message.chat.id, message_id=placeholder_message.message_id)
    except Exception as e:
        logger.error(f"Error sending error message: {e}")
        try:
            bot.send_message(message.chat.id, response)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
