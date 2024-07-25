import base64

def download_and_encode_image(bot, file_id: str) -> str:
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    return base64.b64encode(downloaded_file).decode('ascii')
