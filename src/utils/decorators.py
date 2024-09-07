from functools import wraps
from telebot.types import Message
from src.utils.utils import is_authorized

def authorized_only(func):
    @wraps(func)
    def wrapper(bot, message: Message, *args, **kwargs):
        if not is_authorized(message):
            bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
            return
        return func(bot, message, *args, **kwargs)
    return wrapper
