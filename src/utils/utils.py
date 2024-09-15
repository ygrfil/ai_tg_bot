from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import os
from config import ENV
from langchain_core.callbacks import BaseCallbackHandler
import time
import logging
from src.database.database import is_user_allowed, get_user_preferences, get_last_interaction_time, update_last_interaction_time

logger = logging.getLogger(__name__)

def is_authorized(message: Message) -> bool:
    user_id = message.from_user.id
    return is_user_allowed(user_id) or str(user_id) in (ENV.get("ADMIN_USER_IDS") or [])

def reset_conversation_if_needed(user_id: int) -> bool:
    current_time = datetime.now()
    last_interaction_str = get_last_interaction_time(user_id)
    if last_interaction_str:
        last_interaction = datetime.fromisoformat(last_interaction_str)
        if current_time - last_interaction > timedelta(hours=2):
            update_last_interaction_time(user_id, current_time.isoformat())
            return True
    update_last_interaction_time(user_id, current_time.isoformat())
    return False

def get_system_prompt(user_id: int) -> str:
    user_prefs = get_user_preferences(user_id)
    system_prompts = get_system_prompts()
    return system_prompts.get(user_prefs.get('system_prompt', 'standard'), system_prompts['standard'])


def create_keyboard(buttons: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data)] for text, data in buttons])

def get_system_prompts() -> Dict[str, str]:
    prompts = {}
    try:
        for filename in os.listdir('system_prompts'):
            if filename.endswith('.txt'):
                with open(os.path.join('system_prompts', filename), 'r') as file:
                    prompt_name = 'standard' if filename == 'standard.txt' else filename[:-4]
                    prompts[prompt_name] = file.read().strip()
    except Exception as e:
        logger.error(f"Error reading system prompts: {e}")
    return prompts

def remove_system_prompt(prompt_name: str) -> bool:
    prompt_path = os.path.join('system_prompts', f"{prompt_name}.txt")
    if os.path.exists(prompt_path):
        try:
            os.remove(prompt_path)
            return True
        except OSError as e:
            logger.error(f"Error removing system prompt: {e}")
            return False
    return False

def get_username(bot: Any, user_id: int) -> str:
    try:
        user = bot.get_chat(user_id)
        return user.username or f"{user.first_name} {user.last_name}".strip() or f"User {user_id}"
    except Exception as e:
        logger.error(f"Error getting username: {e}")
        return f"User {user_id}"

def get_user_id(bot: Any, user_input: str) -> Optional[int]:
    if user_input.isdigit():
        return int(user_input)
    elif user_input.startswith('@'):
        try:
            chat = bot.get_chat(user_input)
            return chat.id
        except Exception as e:
            logger.error(f"Error getting user ID: {e}")
            return None
    else:
        return None

class StreamHandler:
    def __init__(self, bot: Any, chat_id: int, message_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.response = ""
        self.last_update_time = time.time()
        self.update_interval = 0.3
        self.max_message_length = 4096

    def on_llm_new_token(self, token: str) -> None:
        self.response += token
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_interval:
            self.update_message()
            self.last_update_time = current_time

    def update_message(self) -> None:
        try:
            update_text = self.response[-self.max_message_length:] if len(self.response) > self.max_message_length else self.response
            if update_text.strip():
                try:
                    self.bot.edit_message_text(update_text, chat_id=self.chat_id, message_id=self.message_id)
                except Exception as e:
                    if "message is not modified" not in str(e).lower():
                        logger.error(f"Error updating message: {e}")
                self.last_update_time = time.time()
        except Exception as e:
            logger.error(f"Error updating message: {e}")

    def on_llm_end(self, response: str, **kwargs) -> None:
        self.update_message()
