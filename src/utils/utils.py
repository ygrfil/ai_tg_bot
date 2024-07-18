from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from config import ENV
from langchain.callbacks.base import BaseCallbackHandler
import time
from src.database.database import is_user_allowed, get_user_preferences

last_interaction_time = {}

def is_authorized(message) -> bool:
    user_id = message.from_user.id
    return is_user_allowed(user_id) or str(user_id) in ENV["ADMIN_USER_IDS"]

def reset_conversation_if_needed(user_id: int) -> None:
    if datetime.now() - last_interaction_time.get(user_id, datetime.min) > timedelta(minutes=150):
        return True
    last_interaction_time[user_id] = datetime.now()
    return False

def get_system_prompt(user_id: int) -> str:
    user_prefs = get_user_preferences(user_id)
    system_prompts = get_system_prompts()
    return system_prompts.get(user_prefs.get('system_prompt', 'standard'), system_prompts['standard'])

def limit_conversation_history(user_id: int, history: list, max_length: int = 10) -> list:
    if len(history) > max_length:
        return [history[0]] + history[-max_length+1:]
    return history

def create_keyboard(buttons) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data)] for text, data in buttons])

def get_system_prompts():
    prompts = {}
    for filename in os.listdir('system_prompts'):
        if filename.endswith('.txt'):
            with open(os.path.join('system_prompts', filename), 'r') as file:
                prompt_name = 'standard' if filename == 'standard.txt' else filename[:-4]
                prompts[prompt_name] = file.read().strip()
    return prompts

def remove_system_prompt(prompt_name: str) -> bool:
    prompt_path = os.path.join('system_prompts', f"{prompt_name}.txt")
    if os.path.exists(prompt_path):
        try:
            os.remove(prompt_path)
            return True
        except OSError:
            return False
    return False

def get_username(bot, user_id):
    try:
        user = bot.get_chat_member(user_id, user_id).user
        return user.username or f"{user.first_name} {user.last_name}".strip() or f"User {user_id}"
    except Exception:
        return f"Unknown User ({user_id})"

def get_user_id(bot, user_input):
    if user_input.isdigit():
        return int(user_input)
    elif user_input.startswith('@'):
        try:
            chat = bot.get_chat(user_input)
            return chat.id
        except Exception:
            return None
    else:
        return None

class StreamHandler(BaseCallbackHandler):
    def __init__(self, bot, chat_id, message_id):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.response = ""
        self.last_update_time = time.time()
        self.update_interval = 0.3
        self.max_message_length = 4096

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.response += token
        if time.time() - self.last_update_time >= self.update_interval:
            self.update_message()

    def update_message(self):
        try:
            update_text = self.response[-self.max_message_length:] if len(self.response) > self.max_message_length else self.response
            if update_text.strip():
                try:
                    self.bot.edit_message_text(update_text, chat_id=self.chat_id, message_id=self.message_id)
                except Exception as e:
                    if "message is not modified" not in str(e).lower():
                        raise
                self.last_update_time = time.time()
        except Exception as e:
            print(f"Error updating message: {e}")

    def on_llm_end(self, response: str, **kwargs) -> None:
        self.update_message()
