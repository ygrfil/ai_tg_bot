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
        KeyboardButton(text="🗑 Clear History"),
        KeyboardButton(text="₿")
    )
    if is_admin:
        builder.row(KeyboardButton(text="👑 Admin"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Stats"),
        KeyboardButton(text="📢 Broadcast")
    )
    builder.row(KeyboardButton(text="🔙 Back"))
    return builder.as_markup(resize_keyboard=True)

def get_provider_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    
    # Create pairs of providers
    providers = list(PROVIDER_MODELS.keys())
    for i in range(0, len(providers), 2):
        row_buttons = [providers[i].capitalize()]
        if i + 1 < len(providers):
            row_buttons.append(providers[i + 1].capitalize())
        builder.row(*[KeyboardButton(text=btn) for btn in row_buttons])
    
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
