import re
from aiogram import Router, F, types
from aiogram.types import Message, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
import aiohttp
from datetime import datetime
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
from bot.services.ai_providers.fal import FalProvider
from bot.states import UserStates

router = Router()
storage = Storage("data/chat.db")
config = Config.from_env()
rate_limiter = MessageRateLimiter()

# Initialize database on startup
async def init_storage():
    await storage.ensure_initialized()

# Create event loop and run initialization
loop = asyncio.get_event_loop()
loop.run_until_complete(init_storage())

class UserStates(StatesGroup):
    """States for user interaction with the bot."""
    chatting = State()         # Default state for general chat
    choosing_provider = State() # State when user is selecting AI provider
    admin_menu = State()       # State for admin menu
    broadcasting = State()     # State for broadcasting messages
    user_management = State()  # State for user management
    settings_menu = State()    # State for bot settings
    waiting_for_image_prompt = State()  # State for waiting for image prompt

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
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
    return await storage.get_user_settings(user_id)

async def update_keyboard(bot, user_id: int, keyboard: ReplyKeyboardMarkup):
    """Update keyboard by editing the last bot message"""
    try:
        messages = [msg async for msg in bot.get_chat_history(user_id, limit=10)]
        for msg in messages:
            if msg.from_user.is_bot and msg.reply_markup:
                try:
                    await msg.edit_reply_markup(reply_markup=keyboard)
                    return True
                except Exception:
                    continue
    except Exception as e:
        logging.debug(f"Could not update keyboard for user {user_id}: {e}")
    return False

async def send_minimal_message(message: Message, text: str = ".", keyboard: ReplyKeyboardMarkup = None):
    """Send a message with minimal visible content"""
    try:
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logging.debug(f"Failed to send minimal message: {e}")
        # Try with a single dot if empty string fails
        if text == "":
            await message.answer(".", reply_markup=keyboard)

# Command handlers first
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        return
        
    settings = await get_or_create_settings(message.from_user.id)
    is_admin = str(message.from_user.id) == config.admin_id

    await state.clear()  # Clear any existing state
    await state.set_state(UserStates.chatting)  # Set initial state
    
    # Set default model if no provider is selected
    if not settings or 'current_provider' not in settings:
        # Use gpt-4.1 as the default model
        default_provider = "gpt-4.1"
        settings = settings or {}
        settings['current_provider'] = default_provider
        settings['current_model'] = PROVIDER_MODELS[default_provider]['name']
        await storage.save_user_settings(message.from_user.id, settings)
        
        # Log model selection as usage
        await storage.log_usage(
            user_id=message.from_user.id,
            provider=default_provider,
            model=PROVIDER_MODELS[default_provider]['name'],
            tokens=0,
            has_image=False
        )
        
    await message.answer(
        f"Welcome, {hbold(message.from_user.full_name)}!\n"
        f"Current AI: {settings['current_provider']} "
        f"({settings['current_model']})\n\n"
        "You can start chatting now or use the menu buttons below.",
        reply_markup=kb.get_main_menu(is_admin=is_admin)
    )

# Button handlers (put these BEFORE the general message handler)
@router.message(UserStates.choosing_provider)
async def handle_provider_choice(message: Message, state: FSMContext):
    # Clean up user input and map to provider
    clean_text = message.text.strip().lower()
    provider = None
    
    # Map display names to provider keys
    display_to_provider = {
        'online🌐': 'online',
        'gemini 2.5': 'gemini',
        'gpt-4.1': 'gpt-4.1',
        'sonnet': 'sonnet'
    }
    
    # Try exact match first
    if clean_text in PROVIDER_MODELS:
        provider = clean_text
    else:
        # Try without emojis/special characters
        clean_text = re.sub(r'[🌐🏆\(\)]\s*', '', clean_text).strip()
        # Try to match with display names
        provider = display_to_provider.get(clean_text)
        if not provider:
            # Try partial match with provider names
            for model_name in PROVIDER_MODELS.keys():
                if clean_text in model_name.lower():
                    provider = model_name
                    break
    
    if provider and provider in PROVIDER_MODELS:
        settings = await get_or_create_settings(message.from_user.id)
        if not settings:
            settings = {}
            
        settings['current_provider'] = provider
        settings['current_model'] = PROVIDER_MODELS[provider]['name']
        
        await storage.save_user_settings(
            message.from_user.id,
            settings
        )
        
        # Log model selection as usage
        await storage.log_usage(
            user_id=message.from_user.id,
            provider=provider,
            model=PROVIDER_MODELS[provider]['name'],
            tokens=0,
            has_image=False
        )
        
        await message.answer(
            f"AI Model changed to {PROVIDER_MODELS[provider]['name']}. Ready to chat!",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
        await state.set_state(UserStates.chatting)
    else:
        await message.answer(
            "Please select a model from the menu.",
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
    
    if not settings or 'current_provider' not in settings:
        # Set default model if no provider is selected
        default_provider = "gpt-4.1"
        settings = settings or {}
        settings['current_provider'] = default_provider
        settings['current_model'] = PROVIDER_MODELS[default_provider]['name']
        await storage.save_user_settings(message.from_user.id, settings)
        
        # Log model selection as usage
        await storage.log_usage(
            user_id=message.from_user.id,
            provider=default_provider,
            model=PROVIDER_MODELS[default_provider]['name'],
            tokens=0,
            has_image=False
        )
        
        await message.answer(
            f"ℹ️ Using default AI configuration:\n\n"
            f"Provider: {settings['current_provider']}\n"
            f"Model: {settings['current_model']}\n\n"
            f"You can change it using the '🤖 Choose AI Model' button.",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
    else:
        await message.answer(
            f"ℹ️ Current Configuration:\n\n"
            f"Provider: {settings['current_provider']}\n"
            f"Model: {settings['current_model']}",
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
                
                time = datetime.now().strftime("%H:%M")  # Removed seconds
                
                await message.answer(
                    f"<b>Bitcoin Price:</b>\n\n"
                    f"🔼 <b>24h:</b> ${high_24h:,.0f}\n"
                    f"💰 <b>Now:</b> <code>${current_price:,.0f}</code>\n"
                    f"🔽 <b>24h:</b> ${low_24h:,.0f}\n"
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

@router.message(F.text == "🎨 Generate Image")
async def handle_generate_image_button(message: Message, state: FSMContext):
    """Handle the generate image button click."""
    await state.set_state(UserStates.waiting_for_image_prompt)
    await message.answer(
        "Please enter a prompt describing the image you want to generate.\n"
        "For example: 'A serene mountain landscape at sunset with snow-capped peaks'"
    )

@router.message(UserStates.waiting_for_image_prompt)
async def handle_image_prompt(message: Message, state: FSMContext):
    """Handle the image generation prompt."""
    try:
        # Initialize Fal provider
        provider = get_provider("fal", config)
        if not isinstance(provider, FalProvider):
            await message.answer(
                "❌ Error: Image generation provider not available.",
                reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
            )
            await state.set_state(UserStates.chatting)
            return

        # Send a processing message
        processing_msg = await message.answer("🎨 Generating your image...")
        
        try:
            # Generate the image
            image_url = await provider.generate_image(
                prompt=message.text,
                width=1024,
                height=1024,
                num_inference_steps=50,
                guidance_scale=7.5
            )
            
            if image_url:
                # Send the generated image
                await message.answer_photo(
                    photo=image_url,
                    caption=f"Generated image based on prompt:\n{message.text}",
                    reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
                )
                
                # Log usage
                await storage.log_usage(
                    user_id=message.from_user.id,
                    provider="fal",
                    model="fal-stable-diffusion",
                    tokens=0,
                    has_image=True
                )
            else:
                await message.answer(
                    "Sorry, I couldn't generate the image. Please try again with a different prompt.",
                    reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
                )
        finally:
            # Always try to delete the processing message
            try:
                await processing_msg.delete()
            except:
                pass
        
        # Reset state back to chatting
        await state.set_state(UserStates.chatting)
        
    except Exception as e:
        error_message = str(e)
        if "API key" in error_message.lower():
            error_message = "Missing or invalid API key for image generation."
        elif "quota" in error_message.lower():
            error_message = "Image generation quota exceeded. Please try again later."
            
        await message.answer(
            f"❌ {error_message}",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
        await state.set_state(UserStates.chatting)

# Chat handler for normal messages
@router.message(UserStates.chatting)
async def handle_message(message: Message, state: FSMContext):
    try:
        user = message.from_user
        if str(user.id) not in config.allowed_user_ids:
            return

        # Update user information with each message
        await storage.ensure_user_exists(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )

        # Get settings and history concurrently
        settings_task = storage.get_user_settings(message.from_user.id)
        history_task = storage.get_chat_history(message.from_user.id, limit=20)
        
        settings, history = await asyncio.gather(settings_task, history_task)
        
        if not settings or 'current_provider' not in settings:
            # Set default model if no provider is selected
            default_provider = "gpt-4.1"
            settings = settings or {}
            settings['current_provider'] = default_provider
            settings['current_model'] = PROVIDER_MODELS[default_provider]['name']
            await storage.save_user_settings(message.from_user.id, settings)
            
            # Log model selection as usage
            await storage.log_usage(
                user_id=message.from_user.id,
                provider=default_provider,
                model=PROVIDER_MODELS[default_provider]['name'],
                tokens=0,
                has_image=False
            )
            
            # Notify user about default model
            await message.answer(
                f"Using default model: {settings['current_model']}. You can change it using the '🤖 Choose AI Model' button."
            )

        # Map legacy provider names to new ones
        legacy_to_new = {
            'openai': 'gpt-4.1',
            'claude': 'sonnet',
            'openrouter_deepseek': 'gemini',
            'groq': 'gpt-4.1',
            'o3-mini': 'online',  # Map o3-mini to online
            'r1-1776': 'gemini',
            'online': 'online'  # Ensure online maps to itself
        }
            
        provider_name = legacy_to_new.get(settings['current_provider'], settings['current_provider'])
        if provider_name not in PROVIDER_MODELS:
            await message.answer(
                "🔄 Your selected AI model is no longer available. Please choose a new one:",
                reply_markup=kb.get_provider_menu()
            )
            await state.set_state(UserStates.choosing_provider)
            return
            
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
        token_count = 0
        async for response_chunk in ai_provider.chat_completion_stream(
            message=message_text,
            model_config=model_config,
            history=history,
            image=image_data
        ):
            if response_chunk and response_chunk.strip():
                collected_response += response_chunk
                token_count += len(response_chunk.split())  # Rough token count estimation
                sanitized_response = sanitize_html_tags(collected_response)
                if await rate_limiter.should_update_message(sanitized_response):
                    try:
                        await bot_response.edit_text(sanitized_response, parse_mode="HTML")
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        if "message is not modified" not in str(e).lower():
                            logging.debug(f"Message update error: {e}")

        # Save final response
        if collected_response:
            await storage.add_to_history(message.from_user.id, collected_response, True)
            
            # Log usage statistics
            await storage.log_usage(
                user_id=message.from_user.id,
                provider=provider_name,
                model=model_config['name'],
                tokens=token_count,
                has_image=bool(image_data)
            )
            
            final_response = sanitize_html_tags(collected_response)
            try:
                await bot_response.edit_text(final_response, parse_mode="HTML")
            except Exception as e:
                logging.debug(f"Final message update error: {e}")

    except Exception as e:
        logging.error(f"Error in handle_message: {e}", exc_info=True)
        await message.answer(
            "❌ An error occurred. Please try again later.",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )

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
    
    current_state = await state.get_state()
    if not current_state:
        settings = await storage.get_user_settings(message.from_user.id)
        
        # Set default model if needed
        if not settings or 'current_provider' not in settings:
            # Set default model
            default_provider = "gpt-4.1"
            settings = settings or {}
            settings['current_provider'] = default_provider
            settings['current_model'] = PROVIDER_MODELS[default_provider]['name']
            await storage.save_user_settings(message.from_user.id, settings)
            
            # Log model selection
            await storage.log_usage(
                user_id=message.from_user.id,
                provider=default_provider,
                model=PROVIDER_MODELS[default_provider]['name'],
                tokens=0,
                has_image=False
            )
        
        is_admin = str(message.from_user.id) == config.admin_id
        keyboard = kb.get_main_menu(is_admin)
        
        # Update keyboard silently
        try:
            updated = await update_keyboard(message.bot, message.from_user.id, keyboard)
            if not updated:
                await message.answer("Please select an option:", reply_markup=keyboard)
        except Exception as e:
            logging.debug(f"Keyboard update error: {e}")
            await message.answer("Please select an option:", reply_markup=keyboard)
        
        # Set state to chatting since we always have a default model now
        await state.set_state(UserStates.chatting)