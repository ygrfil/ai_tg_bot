from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
from aiogram.utils.chat_action import ChatActionSender
import base64
from io import BytesIO
import aiohttp
from datetime import datetime, timezone

from ..keyboards import reply as kb
from ..services.storage import JsonStorage
from ..services.ai_providers import get_provider

router = Router()
storage = JsonStorage("data/user_settings.json")

# One model per provider
PROVIDER_MODELS = {
    "openai": {
        "name": "gpt-4o",
        "vision": True
    },
    "groq": {
        "name": "llama-3.2-90b-vision-preview",
        "vision": True
    },
    "claude": {
        "name": "claude-3-5-sonnet-20241022",
        "vision": True
    },
    "perplexity": {
        "name": "llama-3.1-sonar-huge-128k-online",
        "vision": False
    }
}

class UserStates(StatesGroup):
    chatting = State()
    choosing_provider = State()

def log_message(msg: str):
    print(f"\n[DEBUG] {msg}")

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not storage.is_user_allowed(message.from_user.id):
        await message.answer("Sorry, you don't have access to this bot.")
        return

    user_settings = storage.get_user_settings(message.from_user.id)
    if not user_settings:
        # First time user
        await message.answer(
            f"👋 Welcome to AI Assistant Bot!\n\n"
            f"Hello, {hbold(message.from_user.full_name)}!\n\n"
            f"This bot provides access to various AI models including:\n"
            f"• OpenAI GPT-4\n"
            f"• Claude 3\n"
            f"• Groq\n"
            f"• Perplexity\n\n"
            f"Click the button below to start!",
            reply_markup=kb.get_welcome_keyboard()
        )
        return

    # Returning user
    await message.answer(
        f"Welcome back, {hbold(message.from_user.full_name)}!\n"
        f"Current AI: {user_settings['current_provider']} ({user_settings['current_model']})",
        reply_markup=kb.get_main_menu()
    )
    await state.set_state(UserStates.chatting)

@router.message(F.text == "🚀 Start Bot")
async def handle_start_button(message: Message, state: FSMContext):
    default_provider = "groq"
    user_settings = {
        "current_provider": default_provider,
        "current_model": PROVIDER_MODELS[default_provider]["name"]
    }
    storage.update_user_settings(message.from_user.id, user_settings)
    
    await message.answer(
        f"✨ Great! I'm ready to help you!\n\n"
        f"Current AI: {user_settings['current_provider']} ({user_settings['current_model']})\n\n"
        f"You can:\n"
        f"• Send text messages to chat with AI\n"
        f"• Send images for analysis (with supported models)\n"
        f"• Change AI models using '🤖 Choose AI Model'\n"
        f"• Clear conversation history with '🗑 Clear History'",
        reply_markup=kb.get_main_menu()
    )
    await state.set_state(UserStates.chatting)

@router.message(F.text == "🤖 Choose AI Model")
async def choose_model_button(message: Message, state: FSMContext):
    settings = storage.get_user_settings(message.from_user.id)
    await message.answer(
        f"Current provider: {settings['current_provider']}\n"
        f"Current model: {settings['current_model']}\n\n"
        "Choose new provider:",
        reply_markup=kb.get_provider_menu()
    )
    await state.set_state(UserStates.choosing_provider)

@router.message(F.text == "⚙️ Settings")
async def settings_button(message: Message):
    settings = storage.get_user_settings(message.from_user.id)
    provider_name = settings['current_provider']
    vision_capable = "✅" if PROVIDER_MODELS[provider_name]["vision"] else "❌"
    await message.answer(
        f"Current settings:\n"
        f"Provider: {provider_name}\n"
        f"Model: {settings['current_model']}\n"
        f"Vision capability: {vision_capable}",
        reply_markup=kb.get_main_menu()
    )

@router.message(StateFilter(UserStates.choosing_provider))
async def handle_provider_selection(message: Message, state: FSMContext):
    if message.text == "🔙 Back":
        await message.answer(
            "Back to chat mode",
            reply_markup=kb.get_main_menu()
        )
        await state.set_state(UserStates.chatting)
        return

    if message.text not in ["OpenAI", "Groq", "Claude", "Perplexity"]:
        await message.answer("Please select a valid provider")
        return

    provider_name = message.text.lower()
    user_settings = storage.get_user_settings(message.from_user.id)
    
    user_settings.update({
        "current_provider": provider_name,
        "current_model": PROVIDER_MODELS[provider_name]["name"]
    })
    
    storage.update_user_settings(message.from_user.id, user_settings)
    
    await message.answer(
        f"AI provider set to {message.text}\n"
        f"Model: {PROVIDER_MODELS[provider_name]['name']}\n"
        "You can start chatting!",
        reply_markup=kb.get_main_menu()
    )
    await state.set_state(UserStates.chatting)

@router.message(F.text == "🗑 Clear History")
async def clear_history_command(message: Message):
    try:
        if storage.clear_history(message.from_user.id):
            settings = storage.get_user_settings(message.from_user.id)
            await message.answer(
                "✅ Conversation history cleared!\n"
                f"Current AI: {settings.get('current_provider', 'groq')} "
                f"({settings.get('current_model', 'default')})"
            )
        else:
            await message.answer("❌ Error: Could not clear history")
    except Exception as e:
        await message.answer(f"Error clearing history: {str(e)}")

@router.message(F.text == "₿")
async def btc_price_button(message: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.kraken.com/0/public/Ticker?pair=XBTUSD') as response:
                data = await response.json()
                price = int(float(data['result']['XXBTZUSD']['c'][0]))
                now = datetime.now(timezone.utc)
                date = now.strftime("%Y-%m-%d")
                time = now.strftime("%H:%M")
                
                await message.answer(
                    f"🕒 {date} {time}\n"
                    f"💰 BTC/USD <b>${price:,}</b>",
                    reply_markup=kb.get_main_menu(),
                    parse_mode="HTML"
                )
    except Exception as e:
        await message.answer(
            "Sorry, couldn't fetch BTC price. Please try again later.",
            reply_markup=kb.get_main_menu()
        )

@router.message()
async def handle_message(message: Message):
    if not storage.is_user_allowed(message.from_user.id):
        return
        
    # Skip handling button texts
    if message.text in ["🤖 Choose AI Model", "⚙️ Settings", "🗑 Clear History", "₿"]:
        return

    settings = storage.get_user_settings(message.from_user.id)
    if not settings:
        default_provider = "groq"
        settings = {
            "current_provider": default_provider,
            "current_model": PROVIDER_MODELS[default_provider]["name"]
        }
        storage.update_user_settings(message.from_user.id, settings)

    provider = get_provider(settings['current_provider'])
    history = storage.get_history(message.from_user.id)
    
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        try:
            # Handle image if present
            if message.photo and PROVIDER_MODELS[settings['current_provider']]["vision"]:
                photo = message.photo[-1]
                file = await message.bot.get_file(photo.file_id)
                file_path = file.file_path
                file_bytes = await message.bot.download_file(file_path)
                image_bytes = file_bytes.read()
                
                # Convert image bytes to base64 for JSON storage
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                
                # Store user message with base64 encoded image
                storage.add_to_history(
                    message.from_user.id,
                    {
                        "is_bot": False,
                        "content": message.caption or "What's in this image?",
                        "image": base64_image,
                        "image_id": photo.file_id
                    }
                )
                
                response = await provider.generate_response(
                    prompt=message.caption or "What's in this image?",
                    model=settings['current_model'],
                    history=None if settings['current_provider'] == "perplexity" else history,
                    image=image_bytes
                )
            elif message.text:
                # Store user message
                storage.add_to_history(
                    message.from_user.id,
                    {
                        "is_bot": False,
                        "content": message.text
                    }
                )
                
                response = await provider.generate_response(
                    prompt=message.text,
                    model=settings['current_model'],
                    history=None if settings['current_provider'] == "perplexity" else history
                )
            else:
                return
                
            # Store bot response
            storage.add_to_history(
                message.from_user.id,
                {
                    "is_bot": True,
                    "content": response,
                    "provider": settings['current_provider'],
                    "model": settings['current_model']
                }
            )
            
            await message.answer(response)
        except Exception as e:
            await message.answer(f"Error generating response: {str(e)}")

@router.message(Command("history"))
async def show_history(message: Message):
    history = storage.get_history(message.from_user.id)
    if not history:
        await message.answer("No conversation history yet.")
        return
        
    response = "Conversation History:\n\n"
    for msg in history:
        prefix = "🤖" if msg["is_bot"] else "👤"
        provider = f" ({msg['provider']})" if msg.get("provider") else ""
        content = msg["content"]
        if msg.get("image"):
            content = "[Image] " + content
        response += f"{prefix}{provider}: {content}\n\n"
    
    await message.answer(response)
