import base64
from telebot.types import Message

def download_and_encode_image(bot, file_id: str) -> str:
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    return base64.b64encode(downloaded_file).decode('ascii')

def process_image_message(message: Message, bot, selected_model: str) -> dict:
    file_id = message.photo[-1].file_id
    image_base64 = download_and_encode_image(bot, file_id)
    
    if selected_model == 'openai':
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
        }
    else:
        image_url = f"data:image/jpeg;base64,{image_base64}"
        return {
            "type": "image_url",
            "image_url": {"url": image_url},
        }
