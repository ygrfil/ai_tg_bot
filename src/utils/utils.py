from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import os
from config import ENV
import time
import logging
from src.database.database import is_user_allowed, get_user_preferences, get_last_interaction_time, update_last_interaction_time
import requests
import base64

logger = logging.getLogger(__name__)

def is_authorized(message: Message) -> bool:
    """Check if user is authorized."""
    user_id = str(message.from_user.id)
    return is_user_allowed(int(user_id)) or user_id in ENV.get("ADMIN_USER_IDS", [])

def should_reset_conversation(user_id: int) -> bool:
    """Check if conversation should be reset based on time."""
    current_time = datetime.now()
    last_interaction = get_last_interaction_time(user_id)
    if not last_interaction:
        return False
    
    time_diff = current_time - datetime.fromisoformat(last_interaction)
    update_last_interaction_time(user_id, current_time.isoformat())
    return time_diff > timedelta(hours=2)

def get_system_prompt(user_id: int) -> str:
    user_prefs = get_user_preferences(user_id)
    system_prompts = get_system_prompts()
    return system_prompts.get(user_prefs.get('system_prompt', 'standard'), system_prompts['standard'])

def create_keyboard(buttons: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data)] for text, data in buttons])

def get_system_prompts() -> Dict[str, str]:
    prompts = {}
    for filename in os.listdir('system_prompts'):
        if filename.endswith('.txt'):
            with open(os.path.join('system_prompts', filename), 'r') as file:
                prompt_name = 'standard' if filename == 'standard.txt' else filename[:-4]
                prompts[prompt_name] = file.read().strip()
    return prompts

def remove_system_prompt(prompt_name: str) -> bool:
    prompt_path = os.path.join('system_prompts', f"{prompt_name}.txt")
    try:
        os.remove(prompt_path)
        return True
    except OSError as e:
        logger.error(f"Error removing system prompt: {e}")
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
            return bot.get_chat(user_input).id
        except Exception as e:
            logger.error(f"Error getting user ID: {e}")
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
        if time.time() - self.last_update_time >= self.update_interval:
            self.update_message()

    def update_message(self) -> None:
        update_text = self.response[-self.max_message_length:]
        if update_text.strip():
            try:
                self.bot.edit_message_text(update_text, chat_id=self.chat_id, message_id=self.message_id)
                self.last_update_time = time.time()
            except Exception as e:
                if "message is not modified" not in str(e).lower():
                    logger.error(f"Error updating message: {e}")

    def on_llm_end(self, response: str, **kwargs) -> None:
        self.response = response
        self.update_message()

def download_and_encode_image(bot: Any, file_id: str) -> str:
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
    response = requests.get(file_url)
    response.raise_for_status()
    return base64.b64encode(response.content).decode()

def process_image_message(message: Message, bot: Any, selected_model: str) -> Dict[str, Any]:
    file_id = message.photo[-1].file_id
    img_str = download_and_encode_image(bot, file_id)
    
    # Always return in Anthropic format, will be converted if needed
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": img_str
        }
    }
