from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from bot.services.ai_providers.providers import PROVIDER_MODELS

def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🤖 Choose AI Model"),
        KeyboardButton(text="ℹ️ Info")
    )
    builder.row(
        KeyboardButton(text="🎨 Generate Image"),
        KeyboardButton(text="🗑 Clear History")
    )
    builder.row(
        KeyboardButton(text="₿"),
        *([KeyboardButton(text="👑 Admin")] if is_admin else [])
    )
    return builder.as_markup(resize_keyboard=True)

def get_admin_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Stats"),
        KeyboardButton(text="📢 Broadcast")
    )
    builder.row(
        KeyboardButton(text="👥 User Management"),
        KeyboardButton(text="⚙️ Settings")
    )
    builder.row(
        KeyboardButton(text="🔙 Back")
    )
    return builder.as_markup(resize_keyboard=True)

def get_provider_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    
    model_buttons = [
        ["OpenAI", "Sonnet"],
        ["Online🌐", "Gemini 2.5"]
    ]
    
    for row in model_buttons:
        builder.row(*[KeyboardButton(text=text) for text in row])
    
    builder.row(KeyboardButton(text="🔙 Back"))
    return builder.as_markup(resize_keyboard=True)

def get_back_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔙 Back"))
    return builder.as_markup(resize_keyboard=True)

def get_welcome_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🚀 Start Bot"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
