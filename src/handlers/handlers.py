from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from anthropic import Anthropic
import base64
import time
import tempfile
import os
import io
import requests
from config import ENV
from src.database.database import (get_user_preferences, save_user_preferences, ensure_user_preferences,
                      log_usage, get_monthly_usage, get_user_monthly_usage)
from src.models.models import get_llm, get_conversation_messages
from src.utils.utils import (reset_conversation_if_needed, limit_conversation_history,
                   create_keyboard, get_system_prompts, get_username, get_user_id, StreamHandler, is_authorized,
                   remove_system_prompt, get_system_prompt)
from src.database.database import is_user_allowed, get_allowed_users, add_allowed_user, remove_allowed_user

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
    elif command == 'create_prompt':
        create_prompt_command(bot, message)
    elif command == 'list_users':
        handle_list_users(bot, message)
    elif command == 'add_user':
        handle_add_user(bot, message)
    elif command == 'remove_user':
        handle_remove_user(bot, message)
    elif command == 'remove_prompt':
        handle_remove_prompt(bot, message)
    elif command == 'status':
        handle_status(bot, message)

def handle_list_users(bot, message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    
    users = get_allowed_users()
    user_list = []
    for user in users:
        username = get_username(bot, user[0])
        user_list.append(f"ID: {user[0]}, Username: {username}")
    
    user_list_str = "\n".join(user_list)
    bot.reply_to(message, f"List of allowed users:\n{user_list_str}")

def handle_add_user(bot, message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    
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

def handle_remove_user(bot, message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    
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

def handle_remove_prompt(bot, message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    
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
    status_message += f"Total tokens: {usage[1] if usage else 0}\n"
    
    bot.reply_to(message, status_message)

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
    current_user = None
    for user_id, model, messages, tokens in usage_stats:
        if current_user != user_id:
            if current_user is not None:
                usage_report += "\n"
            username = get_username(bot, user_id)
            usage_report += f"User: {username}\n"
            current_user = user_id
        usage_report += f"  Model: {model}\n"
        usage_report += f"    Messages: {messages}\n"
        usage_report += f"    Estimated Tokens: {tokens}\n"
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

def create_prompt_command(bot, message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    bot.reply_to(message, "Please send the name for your new system prompt.")
    bot.register_next_step_handler(message, lambda m: process_prompt_name(bot, m))

def process_prompt_name(bot, message: Message) -> None:
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
    """
    Handle incoming messages from users.
    
    :param bot: The bot instance
    :param message: The incoming message
    """
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    user_id = message.from_user.id
    ensure_user_preferences(user_id)
    user_prefs = get_user_preferences(user_id)
    selected_model = user_prefs['selected_model']

    if user_id not in user_conversation_history:
        system_prompt = get_system_prompt(user_id)
        user_conversation_history[user_id] = []

    placeholder_message = bot.send_message(message.chat.id, "Generating...")

    try:
        user_message = process_message_content(message, bot, selected_model)
        user_conversation_history[user_id].append(user_message)

        stream_handler = StreamHandler(bot, message.chat.id, placeholder_message.message_id)
        llm = get_llm(selected_model, stream_handler, user_id)
        
        messages = get_conversation_messages(user_conversation_history, user_id, selected_model)
        
        if selected_model == 'anthropic' and message.content_type == 'photo':
            ai_message_content = process_image_for_anthropic(message, bot)
        else:
            response = llm.invoke(messages)
            ai_message_content = stream_handler.response
        
        # Debug information
        print(f"Debug - ai_response type: {type(ai_response)}")
        print(f"Debug - ai_message_content type: {type(ai_message_content)}")
        print(f"Debug - ai_message_content: {ai_message_content}")
        
        # Check if ai_message_content is a list
        if isinstance(ai_message_content, list):
            # If it's a list, join the elements into a single string
            ai_message_content = " ".join(map(str, ai_message_content))
        
        # Truncate the message if it's too long
        max_message_length = 4096  # Telegram's maximum message length
        if len(ai_message_content) > max_message_length:
            ai_message_content = ai_message_content[:max_message_length - 3] + "..."
        
        tokens_count = len(ai_message_content.split())

        # Update the placeholder message with the AI response
        try:
            bot.edit_message_text(ai_message_content, chat_id=message.chat.id, message_id=placeholder_message.message_id)
        except Exception as edit_error:
            print(f"Debug - Edit message error: {str(edit_error)}")
            if "message is not modified" in str(edit_error):
                # If the message content is the same, we don't need to update it
                pass
            else:
                # If it's a different error, re-raise it
                raise

        user_conversation_history[user_id].append(AIMessage(content=ai_message_content))

        messages_count = 1
        log_usage(user_id, selected_model, messages_count, tokens_count)
    except Exception as e:
        error_message = "The AI model is currently overloaded. Please try again in a few moments." if 'overloaded_error' in str(e) else f"An error occurred: {str(e)}"
        try:
            bot.edit_message_text(error_message, chat_id=message.chat.id, message_id=placeholder_message.message_id)
        except Exception as send_error:
            print(f"Debug - Send error message error: {str(send_error)}")
            # If editing fails, try sending a new message
            bot.send_message(message.chat.id, error_message)
        print(f"Error in handle_message: {str(e)}")  # Log the error

from anthropic import Anthropic

def process_message_content(message: Message, bot, selected_model: str) -> HumanMessage:
    if message.content_type == 'photo':
        if selected_model == 'anthropic':
            return process_image_for_anthropic(message, bot)
        elif selected_model == 'openai':
            return process_image_for_openai(message, bot)
        else:
            return HumanMessage(content="I'm sorry, but I can't process images with the current model. Please try using the Anthropic or OpenAI model for image analysis.")
    return HumanMessage(content=message.text)

def process_image_for_openai(message: Message, bot) -> HumanMessage:
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        
        content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
        
        if message.caption:
            content.append({
                "type": "text",
                "text": message.caption
            })
        else:
            content.append({
                "type": "text",
                "text": "Please describe this image in detail."
            })
        
        return HumanMessage(content=content)
    except Exception as e:
        print(f"Error in process_image_for_openai: {str(e)}")  # Log the error
        return HumanMessage(content="An error occurred while processing the image. Please try again later.")

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
import base64

def process_image_for_anthropic(message: Message, bot) -> str:
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_base64
                }
            },
            {
                "type": "text",
                "text": message.caption or "Please describe this image in detail."
            }
        ]
        
        chat = ChatAnthropic(model="claude-3-sonnet-20240229")
        response = chat.invoke([HumanMessage(content=content)])
        
        # Extract the first sentence of the response as the image description
        image_description = response.content.split('.')[0] + '.'
        
        return image_description
    except Exception as e:
        print(f"Error in process_image_for_anthropic: {str(e)}")
        return f"An error occurred while processing the image: {str(e)}"
