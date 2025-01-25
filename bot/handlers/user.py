from aiogram import Router, F, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
import aiohttp
from datetime import datetime, timedelta
import logging
from typing import Optional
import asyncio

from bot.keyboards import reply as kb
from bot.services.storage import Storage
from bot.services.ai_providers import get_provider
from bot.config import Config
from bot.utils.message_sanitizer import sanitize_html_tags
from bot.services.ai_providers.providers import PROVIDER_MODELS
from bot.utils.rate_limiter import MessageRateLimiter

router = Router()
storage = Storage("data/chat.db")
config = Config.from_env()
rate_limiter = MessageRateLimiter()

class UserStates(StatesGroup):
    """States for user interaction with the bot."""
    chatting = State()         # Default state for general chat
    choosing_provider = State() # State when user is selecting AI provider
    admin_menu = State()       # State for admin menu
    broadcasting = State()     # New state for broadcasting messages

# Helper functions
def is_user_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot"""
    user_id_str = str(user_id)
    return user_id_str == config.admin_id or user_id_str in config.allowed_user_ids

async def get_or_create_settings(user_id: int, message: Optional[Message] = None) -> Optional[dict]:
    """Get user settings and update username if message is provided"""
    if message and message.from_user:
        await storage.ensure_user_exists(
            user_id=user_id,
            username=message.from_user.username
        )
    return await storage.get_user_settings(user_id)

# Command handlers first
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
        
    settings = await get_or_create_settings(message.from_user.id)
    is_admin = str(message.from_user.id) == config.admin_id

    await state.clear()  # Clear any existing state
    await state.set_state(UserStates.chatting)  # Set initial state
    
    if settings and settings.get('current_provider'):
        await message.answer(
            f"Welcome, {hbold(message.from_user.full_name)}!\n"
            f"Current AI: {settings['current_provider']} "
            f"({settings['current_model']})\n\n"
            "You can start chatting now or use the menu buttons below.",
            reply_markup=kb.get_main_menu(is_admin=is_admin)
        )
    else:
        await message.answer(
            f"Welcome, {hbold(message.from_user.full_name)}!\n"
            "Please select an AI provider to start chatting:",
            reply_markup=kb.get_provider_menu()
        )
        await state.set_state(UserStates.choosing_provider)

# Button handlers (put these BEFORE the general message handler)
@router.message(UserStates.choosing_provider)
async def handle_provider_choice(message: Message, state: FSMContext):
    provider = message.text.lower()
    if provider in PROVIDER_MODELS:  # Use PROVIDER_MODELS directly for validation
        settings = await get_or_create_settings(message.from_user.id)
        if not settings:
            settings = {}
        settings['current_provider'] = provider
        settings['current_model'] = PROVIDER_MODELS[provider]['name']
        
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
        # Show available providers from PROVIDER_MODELS
        # Clean input and validate
        clean_provider = message.text.lower().strip("🏆🌐 ").strip()
        
        if clean_provider in PROVIDER_MODELS:
            # Save settings to persistent storage
            settings = await get_or_create_settings(message.from_user.id)
            settings.update({
                'current_provider': clean_provider,
                'current_model': PROVIDER_MODELS[clean_provider]['name']
            })
            await storage.save_user_settings(message.from_user.id, settings)
            
            await message.answer(
                f"Provider changed to {clean_provider.capitalize()}",
                reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
            )
            await state.set_state(UserStates.chatting)
            return
        
        # Show error with decorated names
        decorated_providers = [
            f"{'🏆 ' if p == 'deepseek' else '🌐 ' if p == 'perplexity' else ''}{p.capitalize()}"
            for p in PROVIDER_MODELS.keys()
        ]
        await message.answer(
            f"Please select a provider from the menu: {', '.join(decorated_providers)}",
            reply_markup=kb.get_provider_menu()
        )

@router.message(F.text == "🤖 Choose AI Model")
async def choose_model_button(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
    
    settings = await get_or_create_settings(message.from_user.id)
    
    if settings and settings.get('current_provider'):
        current_provider = settings['current_provider']
        current_model = settings['current_model']
        await message.answer(
            f"Choose AI Provider:\n\n"
            f"Current provider: {current_provider}\n"
            f"Current model: {current_model}",
            reply_markup=kb.get_provider_menu()
        )
    else:
        await message.answer(
            "Choose AI Provider:",
            reply_markup=kb.get_provider_menu()
        )
    
    await state.set_state(UserStates.choosing_provider)

@router.message(F.text == "ℹ️ Info")
async def info_button(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
    
    settings = await storage.get_user_settings(message.from_user.id)
    
    if settings:
        await message.answer(
            f"ℹ️ Current Configuration:\n\n"
            f"Provider: {settings['current_provider']}\n"
            f"Model: {settings['current_model']}",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
    else:
        await message.answer(
            "ℹ️ No AI provider selected yet.\n"
            "Please choose your provider:",
            reply_markup=kb.get_provider_menu()
        )
        await state.set_state(UserStates.choosing_provider)

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
                
                time = datetime.now().strftime("%H:%M")  # Removed seconds
                
                await message.answer(
                    f"<b>Bitcoin Price:</b>\n\n"
                    f"🔼 <b>24h:</b> ${high_24h:,.0f}\n"  # Minimalistic green arrow for high
                    f"💰 <b>Now:</b> <code>${current_price:,.0f}</code>\n"  # Highlighted current price
                    f"🔽 <b>24h:</b> ${low_24h:,.0f}\n"  # Minimalistic red arrow for low
                    f"📊 <b>24h Volume:</b> {volume:,.2f} BTC\n\n"
                    f"🕒 <b>Time:</b> {time}",
                    reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id),
                    parse_mode='HTML'
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
    try:
        user = message.from_user
        if str(user.id) not in config.allowed_user_ids:
            return

        # Get settings and history concurrently
        settings_task = storage.get_user_settings(message.from_user.id)
        history_task = storage.get_chat_history(message.from_user.id, limit=20)  # Increased history limit
        
        settings, history = await asyncio.gather(settings_task, history_task)
        
        if not settings or 'current_provider' not in settings:
            await message.answer(
                "🤖 Please select an AI Model first:",
                reply_markup=kb.get_provider_menu()
            )
            await state.set_state(UserStates.choosing_provider)
            return
            
        provider_name = settings['current_provider']
        model_config = PROVIDER_MODELS[provider_name]
        
        # Process message and image
        image_data = None
        message_text = message.caption if message.caption else message.text

        if message.photo:
            photo = message.photo[-1]
            image_file = await message.bot.get_file(photo.file_id)
            image_bytes = await message.bot.download_file(image_file.file_path)
            image_data = image_bytes.read()
            
            if not message_text:
                message_text = "Please analyze this image."

        # Add user message to history first
        await storage.add_to_history(message.from_user.id, message_text, False, image_data)

        # Get AI provider and prepare response
        ai_provider = get_provider(provider_name, config)
        await message.bot.send_chat_action(message.chat.id, "typing")
        bot_response = await message.answer("Processing...")
        
        # Stream the response
        collected_response = ""
        async for response_chunk in ai_provider.chat_completion_stream(
            message=message_text,
            model_config=model_config,
            history=history,
            image=image_data
        ):
            if response_chunk and response_chunk.strip():
                collected_response += response_chunk
                logging.debug(f"Received chunk: {response_chunk}")
                sanitized_response = sanitize_html_tags(collected_response)
                if await rate_limiter.should_update_message(sanitized_response):
                    try:
                        await bot_response.edit_text(sanitized_response, parse_mode="HTML")
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        if "message is not modified" not in str(e).lower():
                            logging.warning(f"Message update error: {e}")
                        continue

        # Save AI response to history
        if collected_response:
            await storage.add_to_history(message.from_user.id, collected_response, True)

        # Handle final message update
        if collected_response and collected_response.strip():
            final_response = sanitize_html_tags(collected_response)
            if final_response.strip() != rate_limiter.current_message:
                await MessageRateLimiter.retry_final_update(bot_response, final_response)
            rate_limiter.current_message = None
            logging.info(f"Completed processing message for user {user.id}")

        # Log usage statistics
        await storage.log_usage(
            user_id=message.from_user.id,
            provider=provider_name,
            model=model_config['name'],
            tokens=len(collected_response.split()),
            has_image=bool(image_data)
        )

    except Exception as e:
        logging.error(f"Error in handle_message: {e}", exc_info=True)
        await message.answer("❌ An error occurred. Please try again later.")

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