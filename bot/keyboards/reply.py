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
        KeyboardButton(text="👥 Users"),
        KeyboardButton(text="⚙️ Settings")
    )
    builder.row(KeyboardButton(text="🔙 Back"))
    return builder.as_markup(resize_keyboard=True)

def get_provider_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    
    # Get available provider models
    available_models = list(PROVIDER_MODELS.keys())
    
    # Filter out fal which is only for image generation
    available_models = [model for model in available_models if model != "fal"]
    
    # Create nice display names for models
    display_names = {
        "openai": "OpenAI",
        "sonnet": "Sonnet",
        "online": "Online🌐",
        "gemini": "Gemini 2.5"
    }
    
    # Build rows with 2 buttons each
    row = []
    for model in sorted(available_models):
        row.append(KeyboardButton(text=display_names.get(model, model.capitalize())))
        if len(row) == 2:
            builder.row(*row)
            row = []
    
    # Add any remaining buttons
    if row:
        builder.row(*row)
    
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
