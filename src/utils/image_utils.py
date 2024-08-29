import base64
from typing import Dict, Any
from telebot.types import Message
from telebot import TeleBot
from telebot.apihelper import ApiException

def download_and_encode_image(bot: TeleBot, file_id: str) -> str:
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        return base64.b64encode(downloaded_file).decode('ascii')
    except ApiException as e:
        raise ValueError(f"Failed to download image: {str(e)}")

def process_image_message(message: Message, bot: TeleBot, selected_model: str) -> Dict[str, Any]:
    if not message.photo:
        raise ValueError("No photo found in the message")
    
    file_id = message.photo[-1].file_id
    image_base64 = download_and_encode_image(bot, file_id)
    image_url = f"data:image/jpeg;base64,{image_base64}"
    
    return {
        "type": "image_url",
        "image_url": {"url": image_url},
    }
