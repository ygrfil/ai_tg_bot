from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🤖 Choose AI Model"),
        KeyboardButton(text="⚙️ Settings")
    )
    builder.row(
        KeyboardButton(text="🗑 Clear History"),
        KeyboardButton(text="₿")
    )
    return builder.as_markup(resize_keyboard=True)

def get_provider_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="OpenAI"),
        KeyboardButton(text="Groq")
    )
    builder.row(
        KeyboardButton(text="Claude"),
        KeyboardButton(text="Perplexity")
    )
    builder.row(KeyboardButton(text="🔙 Back"))
    return builder.as_markup(resize_keyboard=True)

def get_back_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔙 Back"))
    return builder.as_markup(resize_keyboard=True)
