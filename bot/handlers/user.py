import re
from aiogram import Router, F, types
from aiogram.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
import aiohttp
from datetime import datetime
import logging
from typing import Optional
import asyncio
import time

from bot.keyboards import reply as kb
from bot.services.storage import Storage
from bot.services.ai_providers import get_provider
from bot.config import Config
from bot.services.ai_providers.providers import PROVIDER_MODELS
from bot.services.ai_providers.fal import FalProvider
from bot.schemas import get_response_schema, detect_response_type
from bot.states import UserStates

router = Router()
storage = Storage("data/chat.db")
config = Config.from_env()

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
        # Use openai as the default model
        default_provider = "openai"
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
        default_provider = "openai"
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
    """Handle the image generation button press"""
    await message.answer(
        "Please provide a detailed prompt describing the image you want to generate.\n\n"
        "Tips for better results:\n"
        "• Be specific about what you want to see\n"
        "• Describe the style (e.g., photorealistic, anime, oil painting)\n"
        "• Mention lighting, camera angle, or mood if relevant\n"
        "• Use 'negative prompt' after -- to specify what to avoid\n\n"
        "Example: A majestic red dragon soaring through storm clouds, digital art style -- blurry, text, watermark",
        reply_markup=kb.ReplyKeyboardBuilder()
            .button(text="🔙 Cancel")
            .adjust(1)
            .as_markup(resize_keyboard=True)
    )
    await state.set_state(UserStates.waiting_for_image_prompt)

@router.message(StateFilter(UserStates.waiting_for_image_prompt))
async def handle_image_prompt(message: Message, state: FSMContext):
    """Handle the image generation prompt"""
    if not is_user_authorized(message.from_user.id):
        return
        
    # Handle cancel button
    if message.text == "🔙 Cancel":
        await state.set_state(UserStates.chatting)
        await message.answer(
            "Image generation cancelled.",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )
        return
        
    prompt = message.text
    negative_prompt = ""
    
    # Split prompt and negative prompt if -- is present
    if " -- " in prompt:
        prompt, negative_prompt = prompt.split(" -- ", 1)
    
    # Get Fal provider for image generation
    provider = await get_provider("fal", config)
    
    # Send a processing message
    processing_msg = await message.answer("🎨 Generating your image...")
    
    try:
        # Generate the image
        result = await provider.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt
        )
        
        if not result:
            raise Exception("Failed to generate image - no result returned")
            
        image_data = None
        # Check if result is a base64 string (starts with data:image)
        if isinstance(result, str) and result.startswith('data:image'):
            # Extract base64 data after the comma
            import base64
            base64_data = result.split(',')[1]
            image_data = base64.b64decode(base64_data)
        else:
            # Treat as URL and download
            async with aiohttp.ClientSession() as session:
                async with session.get(result) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download image: HTTP {response.status}")
                    image_data = await response.read()
        
        if not image_data:
            raise Exception("No image data received")
            
        # Send the generated image
        await message.answer_photo(
            types.BufferedInputFile(
                image_data,
                filename="generated_image.png"
            )
        )
        
        # Log the successful generation
        await storage.add_to_history(
            user_id=message.from_user.id,
            content=f"[Image generation prompt] {prompt}",
            is_bot=False
        )
        await storage.add_to_history(
            user_id=message.from_user.id,
            content="[Generated image]",
            is_bot=True
        )
        
        # Log usage statistics
        await storage.log_usage(
            user_id=message.from_user.id,
            provider="fal",
            model="hidream-i1-full",
            tokens=0,
            has_image=True
        )
        
    except Exception as e:
        error_message = str(e)
        user_friendly_error = "An unexpected error occurred"
        
        # Map common errors to user-friendly messages
        if "API key" in error_message.lower():
            user_friendly_error = "The image generation service is temporarily unavailable"
        elif "quota" in error_message.lower():
            user_friendly_error = "Image generation quota exceeded. Please try again later"
        elif "content policy" in error_message.lower():
            user_friendly_error = "Your prompt was flagged by content filters. Please try a different prompt"
        elif "timeout" in error_message.lower():
            user_friendly_error = "The request timed out. Please try again"
        elif "too many requests" in error_message.lower():
            user_friendly_error = "Too many requests. Please wait a moment and try again"
        elif "download" in error_message.lower() or "no image data" in error_message.lower():
            user_friendly_error = "Failed to process the generated image. Please try again"
            
        await message.answer(f"❌ {user_friendly_error}")
        
        # Log the error for debugging
        logging.error(f"Image generation error: {error_message}")
        
    finally:
        # Delete the processing message and reset state
        await processing_msg.delete()
        await state.set_state(UserStates.chatting)
        await message.answer(
            "You can generate another image or continue chatting.",
            reply_markup=kb.get_main_menu(is_admin=str(message.from_user.id) == config.admin_id)
        )

# Chat handler for normal messages
@router.message(UserStates.chatting)
async def handle_message(message: Message, state: FSMContext):
    try:
        user = message.from_user
        if str(user.id) not in config.allowed_user_ids:
            return

        t0 = time.monotonic()
        
        # Show response immediately to reduce perceived latency
        await message.bot.send_chat_action(message.chat.id, "typing")
        bot_response = await message.answer("💭")
        
        # Get only essential data needed for AI call (minimal context for speed)
        settings_task = storage.get_user_settings(message.from_user.id)
        history_task = storage.get_chat_history(message.from_user.id, limit=6)  # Reduced for speed
        settings, history = await asyncio.gather(settings_task, history_task)
        t1 = time.monotonic()

        if not settings or 'current_provider' not in settings:
            # Set default model if no provider is selected (minimal setup for immediate AI call)
            default_provider = "openai"
            settings = settings or {}
            settings['current_provider'] = default_provider
            settings['current_model'] = PROVIDER_MODELS[default_provider]['name']
            # Save settings in background, don't wait
            asyncio.create_task(storage.save_user_settings(message.from_user.id, settings))

        legacy_to_new = {
            'openai': 'openai',
            'claude': 'sonnet',
            'openrouter_deepseek': 'gemini',
            'groq': 'openai',
            'o3-mini': 'online',
            'r1-1776': 'gemini',
            'online': 'online'
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

        image_data = None
        message_text = message.caption if message.caption else message.text
        if message.photo:
            photo = message.photo[-1]
            image_file = await message.bot.get_file(photo.file_id)
            image_bytes = await message.bot.download_file(image_file.file_path)
            image_data = image_bytes.read()
            if not message_text:
                message_text = "Please analyze this image."

        # Start AI streaming immediately, handle history in background
        ai_provider = await get_provider(provider_name, config)
        
        # Start user creation and history saving in background (don't block AI call)
        asyncio.create_task(storage.ensure_user_exists(
            user_id=user.id, username=user.username, first_name=user.first_name
        ))
        asyncio.create_task(storage.add_to_history(message.from_user.id, message_text, False, image_data))
        
        # Check if we should use structured outputs (for supported models and specific query types)
        use_structured = await should_use_structured_output(message_text, provider_name, image_data is not None)
        
        if use_structured:
            # Use structured output for better reliability
            response_type = detect_response_type(message_text, image_data is not None)
            response_schema = get_response_schema(response_type)
            
            logging.info(f"Using structured output with schema: {response_type}")
            
            try:
                # Get structured response
                structured_response = await ai_provider.chat_completion_structured(
                    message=message_text,
                    model_config=model_config,
                    response_schema=response_schema,
                    history=history,
                    image=image_data
                )
                
                # Extract content and handle the structured response
                await handle_structured_response(message, reply_msg, structured_response, t2)
                return
                
            except Exception as e:
                logging.error(f"Structured output failed, falling back to streaming: {e}")
                # Fall back to regular streaming
        
        # Stream the response immediately (regular mode or fallback)
        collected_response = ""
        token_count = 0
        last_update_length = 0
        t2 = time.monotonic()
        async for response_chunk in ai_provider.chat_completion_stream(
            message=message_text,
            model_config=model_config,
            history=history,
            image=image_data
        ):
            if response_chunk and response_chunk.strip():
                collected_response += response_chunk
                token_count += len(response_chunk.split())
                
                # Only update message every 50 characters
                if len(collected_response) - last_update_length >= 50:
                    try:
                        await bot_response.edit_text(collected_response, parse_mode="HTML")
                        last_update_length = len(collected_response)
                    except Exception as e:
                        if "message is not modified" not in str(e).lower():
                            logging.debug(f"Message update error: {e}")
        t3 = time.monotonic()

        if collected_response:
            # Save response and log usage in background for final cleanup
            asyncio.create_task(storage.add_to_history(message.from_user.id, collected_response, True))
            asyncio.create_task(storage.log_usage(
                user_id=message.from_user.id,
                provider=provider_name,
                model=model_config['name'],
                tokens=token_count,
                has_image=bool(image_data)
            ))
            
            # Update final message if there are remaining characters not shown
            if len(collected_response) > last_update_length:
                try:
                    await bot_response.edit_text(collected_response, parse_mode="HTML")
                except Exception as e:
                    logging.debug(f"Final message update error: {e}")

        t4 = time.monotonic()
        logging.info(f"[TIMING] show_response+load_data: {t1-t0:.3f}s, ai_streaming: {t3-t2:.3f}s, finalize: {t4-t3:.3f}s, total: {t4-t0:.3f}s")

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
            default_provider = "openai"
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
        
        # Update keyboard silently and set state to chatting
        try:
            await update_keyboard(message.bot, message.from_user.id, keyboard)
        except Exception as e:
            logging.debug(f"Keyboard update error: {e}")
        
        # Set state to chatting and redirect to handle_message
        await state.set_state(UserStates.chatting)
        
        # Process the message directly instead of showing "Please select an option"
        await handle_message(message, state)


async def should_use_structured_output(message_text: str, provider_name: str, has_image: bool) -> bool:
    """
    Determine whether to use structured outputs based on message content and provider.
    
    Args:
        message_text: The user's message
        provider_name: Name of the AI provider
        has_image: Whether the message contains an image
        
    Returns:
        True if structured outputs should be used
    """
    # Only use structured outputs for supported providers
    supported_providers = ["sonnet", "openai", "gemini"]
    if provider_name not in supported_providers:
        return False
    
    # Use structured outputs for specific query types that benefit from structure
    message_lower = message_text.lower().strip()
    
    # Always use for help requests and analysis
    if any(keyword in message_lower for keyword in [
        "help", "how to", "tutorial", "guide", "explain how",
        "analyze", "analysis", "compare", "breakdown", "summarize"
    ]):
        return True
    
    # Use for math and code requests
    if any(keyword in message_lower for keyword in [
        "calculate", "solve", "math", "equation", "code", "program", "function"
    ]):
        return True
    
    # Use for image analysis
    if has_image:
        return True
    
    # For now, don't use for general chat to maintain streaming experience
    return False


async def handle_structured_response(message: Message, reply_msg: Message, response_data: dict, start_time: float):
    """
    Handle a structured AI response with appropriate formatting.
    
    Args:
        message: Original user message
        reply_msg: Bot's reply message to update
        response_data: Structured response from AI
        start_time: Start time for performance tracking
    """
    try:
        response_type = response_data.get("response_type", "chat")
        content = response_data.get("content", "No response generated")
        confidence = response_data.get("confidence", 0.0)
        
        # Format response based on type
        if response_type == "code":
            # Format code responses
            lang = response_data.get("programming_language", "")
            explanation = response_data.get("explanation", "")
            formatted_content = f"**{lang.title()} Code:**\n\n```{lang}\n{content}\n```"
            if explanation:
                formatted_content += f"\n\n**Explanation:** {explanation}"
                
        elif response_type == "math":
            # Format math responses with steps
            steps = response_data.get("steps", [])
            final_answer = response_data.get("final_answer", "")
            units = response_data.get("units", "")
            
            formatted_content = f"**Solution:**\n\n"
            for i, step in enumerate(steps, 1):
                formatted_content += f"{i}. {step}\n"
            formatted_content += f"\n**Answer:** {final_answer}"
            if units:
                formatted_content += f" {units}"
                
        elif response_type == "analysis":
            # Format analysis responses
            key_findings = response_data.get("key_findings", [])
            methodology = response_data.get("methodology", "")
            
            formatted_content = f"**Analysis:**\n\n{content}\n\n"
            if key_findings:
                formatted_content += "**Key Findings:**\n"
                for finding in key_findings:
                    formatted_content += f"• {finding}\n"
            if methodology:
                formatted_content += f"\n**Methodology:** {methodology}"
                
        elif response_type == "help":
            # Format help responses
            instructions = response_data.get("instructions", [])
            related_commands = response_data.get("related_commands", [])
            
            formatted_content = f"**Help:** {content}\n\n"
            if instructions:
                formatted_content += "**Instructions:**\n"
                for i, instruction in enumerate(instructions, 1):
                    formatted_content += f"{i}. {instruction}\n"
            if related_commands:
                formatted_content += f"\n**Related commands:** {', '.join(related_commands)}"
                
        elif response_type == "image_analysis":
            # Format image analysis
            objects = response_data.get("objects_detected", [])
            scene = response_data.get("scene_description", "")
            text_content = response_data.get("text_content", "")
            
            formatted_content = f"**Image Analysis:**\n\n{content}\n\n"
            if scene:
                formatted_content += f"**Scene:** {scene}\n"
            if objects:
                formatted_content += f"**Objects detected:** {', '.join(objects)}\n"
            if text_content:
                formatted_content += f"**Text found:** {text_content}\n"
                
        elif response_type == "error":
            # Format error responses
            error_type = response_data.get("error_type", "unknown")
            suggestion = response_data.get("suggestion", "")
            
            formatted_content = f"❌ **Error ({error_type}):** {content}"
            if suggestion:
                formatted_content += f"\n\n💡 **Suggestion:** {suggestion}"
                
        else:
            # Default formatting for chat responses
            formatted_content = content
        
        # Add confidence indicator for low confidence responses
        if confidence < 0.7:
            formatted_content += f"\n\n🤔 *Confidence: {confidence:.1%}*"
        
        # Update message
        await reply_msg.edit_text(formatted_content)
        
        # Log performance
        elapsed = time.monotonic() - start_time
        logging.info(f"Structured response completed in {elapsed:.2f}s (type: {response_type}, confidence: {confidence:.2f})")
        
        # Save to history
        asyncio.create_task(storage.add_to_history(message.from_user.id, final_response, True))
        
    except Exception as e:
        logging.error(f"Error handling structured response: {e}")
        error_msg = "❌ Error processing structured response. Please try again."
        await reply_msg.edit_text(error_msg)


@router.message(Command("structured"))
async def test_structured_command(message: Message, state: FSMContext):
    """Test command for structured outputs."""
    if not is_user_authorized(message.from_user.id):
        return
    
    test_message = message.text.replace("/structured", "").strip()
    if not test_message:
        await message.answer(
            "🧪 **Structured Output Test**\n\n"
            "Usage: `/structured <your question>`\n\n"
            "This will force the use of structured outputs for testing.\n\n"
            "Examples:\n"
            "• `/structured Calculate 15% of 250`\n"
            "• `/structured Write a Python function to reverse a string`\n"
            "• `/structured Analyze the benefits of structured data`"
        )
        return
    
    # Force structured output for testing
    provider_name = await get_user_provider(message.from_user.id)
    ai_provider = await get_provider(provider_name, config)
    model_config = PROVIDER_MODELS[provider_name]
    
    response_type = detect_response_type(test_message, False)
    response_schema = get_response_schema(response_type)
    
    processing_msg = await message.answer("🧪 Testing structured output...")
    
    try:
        start_time = time.monotonic()
        structured_response = await ai_provider.chat_completion_structured(
            message=test_message,
            model_config=model_config,
            response_schema=response_schema,
            history=None,
            image=None
        )
        
        await handle_structured_response(message, processing_msg, structured_response, start_time)
        
    except Exception as e:
        logging.error(f"Structured output test failed: {e}")
        await processing_msg.edit_text(f"❌ Structured output test failed: {str(e)}")


async def get_user_provider(user_id: int) -> str:
    """Get the user's current provider, with fallback to default."""
    try:
        settings = await storage.get_user_settings(user_id)
        if settings and settings.get('current_provider'):
            return settings['current_provider']
    except Exception:
        pass
    return "sonnet"  # Default provider