from aiogram import Router, F, types
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
import aiohttp
from datetime import datetime, timedelta
import logging

from bot.keyboards import reply as kb
from bot.services.storage import Storage
from bot.services.ai_providers import get_provider
from bot.config import Config

router = Router()
storage = Storage("data/chat.db")
config = Config.from_env()

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
    """States for user interaction with the bot."""
    chatting = State()         # Default state for general chat
    choosing_provider = State() # State when user is selecting AI provider

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-4o"

# Helper functions
def is_user_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot"""
    user_id_str = str(user_id)
    return user_id_str == config.admin_id or user_id_str in config.allowed_user_ids

async def get_or_create_settings(user_id: int) -> dict:
    """Get user settings or create default ones"""
    settings = await storage.get_user_settings(user_id)
    if not settings:
        settings = {
            'current_provider': DEFAULT_PROVIDER,
            'current_model': DEFAULT_MODEL
        }
        await storage.save_user_settings(user_id, settings)
    return settings

# Command handlers first
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
        
    settings = await get_or_create_settings(message.from_user.id)
    is_admin = str(message.from_user.id) == config.admin_id

    await state.clear()  # Clear any existing state
    await state.set_state(UserStates.chatting)  # Set initial state
    
    await message.answer(
        f"Welcome, {hbold(message.from_user.full_name)}!\n"
        f"Current AI: {settings.get('current_provider', DEFAULT_PROVIDER)} "
        f"({settings.get('current_model', PROVIDER_MODELS[DEFAULT_PROVIDER]['name'])})\n\n"
        "You can start chatting now or use the menu buttons below.",
        reply_markup=kb.get_main_menu(is_admin=is_admin)
    )

# Button handlers (put these BEFORE the general message handler)
@router.message(UserStates.choosing_provider)
async def handle_provider_choice(message: Message, state: FSMContext):
    # Update available providers list to match PROVIDER_MODELS
    available_providers = ["OpenAI", "Claude", "Groq", "Perplexity"]
    
    if message.text in available_providers:
        settings = await get_or_create_settings(message.from_user.id)
        settings['current_provider'] = message.text.lower()
        settings['current_model'] = PROVIDER_MODELS[settings['current_provider']]['name']
        
        await storage.save_user_settings(
            message.from_user.id, 
            settings
        )
        
        await message.answer(
            f"Provider changed to {message.text}. Ready to chat!",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
        await state.set_state(UserStates.chatting)
    else:
        # Show all available providers in error message
        providers_list = ", ".join(available_providers)
        await message.answer(
            f"Please select a provider from the menu: {providers_list}",
            reply_markup=kb.get_provider_menu()
        )

@router.message(F.text == "🤖 Choose AI Model")
async def choose_model_button(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
    
    settings = await get_or_create_settings(message.from_user.id)
    current_provider = settings.get('current_provider', DEFAULT_PROVIDER)
    current_model = PROVIDER_MODELS[current_provider]['name']
    
    await message.answer(
        f"Choose AI Provider:\n\n"
        f"Current provider: {current_provider}\n"
        f"Current model: {current_model}",
        reply_markup=kb.get_provider_menu()
    )
    await state.set_state(UserStates.choosing_provider)

@router.message(F.text == "⚙️ Settings")
async def settings_button(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
    
    settings = await get_or_create_settings(message.from_user.id)
    current_provider = settings.get('current_provider', DEFAULT_PROVIDER)
    current_model = settings.get('current_model', PROVIDER_MODELS[DEFAULT_PROVIDER]['name'])
    
    await message.answer(
        f"Current Settings:\n\n"
        f"Provider: {current_provider}\n"
        f"Model: {current_model}",
        reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
    )

@router.message(F.text == "🗑 Clear History")
async def clear_history(message: Message):
    if not is_user_authorized(message.from_user.id):
        return
    
    try:
        await storage.clear_user_history(message.from_user.id)
        await message.answer(
            "✅ Chat history cleared!",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
    except Exception as e:
        await message.answer(
            "❌ Error: Could not clear history",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )

@router.message(F.text == "₿")
async def btc_price(message: Message):
    if not is_user_authorized(message.from_user.id):
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.kraken.com/0/public/Ticker?pair=XBTUSD') as response:
                data = await response.json()
                if data.get('error'):
                    raise Exception(data['error'][0])
                    
                price_data = data['result']['XXBTZUSD']
                current_price = float(price_data['c'][0])
                high_24h = float(price_data['h'][1])
                low_24h = float(price_data['l'][1])
                volume = float(price_data['v'][1])
                
                time = datetime.now().strftime("%H:%M:%S")
                
                await message.answer(
                    f"₿ Bitcoin Price (Kraken):\n\n"
                    f"Current: ${current_price:,.2f}\n"
                    f"24h High: ${high_24h:,.2f}\n"
                    f"24h Low: ${low_24h:,.2f}\n"
                    f"24h Volume: {volume:,.2f} BTC\n\n"
                    f"Time: {time}",
                    reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
                )
    except Exception as e:
        await message.answer(
            "❌ Error fetching BTC price from Kraken",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )

@router.message(F.text == "🔙 Back")
async def back_button(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
    
    is_admin = str(message.from_user.id) == config.admin_id
    await message.answer(
        "Main Menu",
        reply_markup=kb.get_main_menu(is_admin=is_admin)
    )
    await state.set_state(UserStates.chatting)

# Chat handler for normal messages (put this AFTER button handlers)
@router.message(UserStates.chatting)
async def handle_message(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return

    try:
        # Ensure user exists in database
        await storage.ensure_user_exists(message.from_user.id)
        
        settings = await get_or_create_settings(message.from_user.id)
        provider_name = settings.get('current_provider', 'openai')
        model_config = PROVIDER_MODELS[provider_name]
        
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Handle image if present
        image_data = None
        message_text = message.text or ""
        
        if message.photo:
            photo = message.photo[-1]
            image_file = await message.bot.get_file(photo.file_id)
            image_bytes = await message.bot.download_file(image_file.file_path)
            image_data = image_bytes.read()
            
            if not message_text:
                message_text = "Please analyze this image."

        # Get chat history and AI provider
        history = await storage.get_chat_history(message.from_user.id)
        ai_provider = get_provider(provider_name, config)
        
        # Send initial response message
        bot_response = await message.answer("...")
        last_update_time = datetime.now()
        update_interval = timedelta(milliseconds=100)  # 100ms between updates
        buffer_size = 50  # characters to buffer before update
        
        collected_response = ""
        last_update_length = 0
        
        # Stream the response
        async for response_chunk in ai_provider.chat_completion_stream(
            message=message_text,
            model_config=model_config,
            history=history,
            image=image_data
        ):
            if response_chunk:
                collected_response += response_chunk
                current_time = datetime.now()
                
                # Update if enough new content AND enough time has passed
                if (len(collected_response) - last_update_length >= buffer_size and 
                    current_time - last_update_time >= update_interval):
                    try:
                        await bot_response.edit_text(collected_response)
                        last_update_length = len(collected_response)
                        last_update_time = current_time
                        
                        # Keep typing indicator active
                        await message.bot.send_chat_action(message.chat.id, "typing")
                    except Exception as e:
                        logging.error(f"Error updating message: {e}")
                        continue
        
        # Final update with complete response
        if collected_response and len(collected_response) > last_update_length:
            try:
                await bot_response.edit_text(collected_response)
                # Save to history
                await storage.add_message(
                    user_id=message.from_user.id,
                    content=collected_response,
                    is_bot=True
                )
            except Exception as e:
                logging.error(f"Error saving final response: {e}")
                
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        await message.answer(
            f"❌ Error processing your message: {str(e)}\n"
            "Please try again or choose a different AI model."
        )

# Unauthorized handler should be last
@router.message()
async def handle_unauthorized(message: Message, state: FSMContext):
    """Handle unauthorized users and unhandled messages"""
    if not is_user_authorized(message.from_user.id):
        await message.answer(
            "⛔️ Access Denied\n\n"
            "Sorry, you don't have permission to use this bot.\n"
            "Please contact the administrator if you need access.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    # For authorized users, check if we're in a state
    current_state = await state.get_state()
    if not current_state:
        # If no state, set to chatting and process as a chat message
        await state.set_state(UserStates.chatting)
        await handle_message(message, state)
    else:
        # If in a state but message not handled by other handlers
        await message.answer(
            "Please use the menu buttons or send a message to chat.",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
