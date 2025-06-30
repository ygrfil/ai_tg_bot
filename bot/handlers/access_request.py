"""
Access request handler for unauthorized users.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from bot.services.storage import Storage
from bot.config import Config

router = Router()
storage = Storage("data/chat.db")
config = Config.from_env()


class AccessRequestState(StatesGroup):
    """States for access request flow."""
    waiting_for_message = State()


def is_user_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot."""
    user_id_str = str(user_id)
    return user_id_str == config.admin_id or user_id_str in config.allowed_user_ids


@router.message(Command("start"), lambda message: not is_user_authorized(message.from_user.id))
async def start_unauthorized(message: Message, state: FSMContext):
    """Handle /start command for unauthorized users."""
    
    user = message.from_user
    can_request = await storage.can_request_access(user.id)
    
    welcome_text = f"👋 Hello {user.first_name or 'there'}!\n\n"
    welcome_text += "🔒 This is a private AI assistant bot.\n\n"
    
    if can_request:
        welcome_text += (
            "📝 You can request access by sending me a message explaining why you'd like to use this bot.\n\n"
            "✨ Use /request to start your access request.\n\n"
            "⏰ Note: You can only make one request per day."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔓 Request Access", callback_data="request_access")
        ]])
    else:
        welcome_text += (
            "⏳ You have already submitted an access request today.\n\n"
            "Please wait for the administrator to review your request.\n\n"
            "🔄 You can try again tomorrow if needed."
        )
        keyboard = None
    
    await message.answer(welcome_text, reply_markup=keyboard)


@router.callback_query(F.data == "request_access")
async def start_access_request(callback_query, state: FSMContext):
    """Start the access request process."""
    if is_user_authorized(callback_query.from_user.id):
        await callback_query.answer("You already have access!", show_alert=True)
        return
    
    user = callback_query.from_user
    can_request = await storage.can_request_access(user.id)
    
    if not can_request:
        await callback_query.answer("You have already requested access today!", show_alert=True)
        return
    
    await callback_query.message.edit_text(
        "📝 **Access Request**\n\n"
        "Please tell me why you'd like to use this AI assistant bot.\n\n"
        "Your message will be sent to the administrator for review.\n\n"
        "💡 Be specific about:\n"
        "• How you plan to use the bot\n"
        "• Why you need access\n"
        "• Any relevant background\n\n"
        "✍️ **Send your request message now:**"
    )
    
    await state.set_state(AccessRequestState.waiting_for_message)
    await callback_query.answer()


@router.message(Command("request"), lambda message: not is_user_authorized(message.from_user.id))
async def request_command(message: Message, state: FSMContext):
    """Handle /request command."""
    
    user = message.from_user
    can_request = await storage.can_request_access(user.id)
    
    if not can_request:
        await message.answer(
            "⏳ You have already submitted an access request today.\n\n"
            "Please wait for the administrator to review your request.\n\n"
            "🔄 You can try again tomorrow if your request is not approved."
        )
        return
    
    await message.answer(
        "📝 **Access Request**\n\n"
        "Please tell me why you'd like to use this AI assistant bot.\n\n"
        "Your message will be sent to the administrator for review.\n\n"
        "💡 Be specific about:\n"
        "• How you plan to use the bot\n"
        "• Why you need access\n" 
        "• Any relevant background\n\n"
        "✍️ **Send your request message now:**"
    )
    
    await state.set_state(AccessRequestState.waiting_for_message)


@router.message(AccessRequestState.waiting_for_message)
async def handle_access_request_message(message: Message, state: FSMContext):
    """Handle the access request message."""
    if is_user_authorized(message.from_user.id):
        await message.answer("✅ You already have access to this bot!")
        await state.clear()
        return
    
    user = message.from_user
    request_message = message.text
    
    # Double-check rate limiting
    can_request = await storage.can_request_access(user.id)
    if not can_request:
        await message.answer(
            "❌ You have already submitted a request today. Please wait until tomorrow to try again."
        )
        await state.clear()
        return
    
    # Submit the access request
    success = await storage.submit_access_request(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        message=request_message
    )
    
    if success:
        await message.answer(
            "✅ **Access request submitted successfully!**\n\n"
            f"📨 Your request has been sent to the administrator.\n\n"
            "⏰ You will be notified when your request is reviewed.\n\n"
            "🔄 You can submit a new request tomorrow if needed.\n\n"
            "Thank you for your patience! 🙏"
        )
        
        # Notify admin about new access request
        await notify_admin_new_request(message.bot, user, request_message)
        
        logging.info(f"Access request submitted by user {user.id} (@{user.username})")
    else:
        await message.answer(
            "❌ **Error submitting access request.**\n\n"
            "Please try again later or contact the administrator directly."
        )
    
    await state.clear()


async def notify_admin_new_request(bot, user, request_message: str):
    """Notify admin about a new access request."""
    try:
        admin_id = int(config.admin_id)
        
        notification_text = (
            f"🔔 **New Access Request**\n\n"
            f"👤 **User:** {user.first_name or 'Unknown'}"
        )
        
        if user.last_name:
            notification_text += f" {user.last_name}"
        
        if user.username:
            notification_text += f" (@{user.username})"
        
        notification_text += f"\n🆔 **ID:** `{user.id}`\n\n"
        notification_text += f"💬 **Message:**\n{request_message}\n\n"
        notification_text += f"⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        notification_text += "📋 Use /admin to review and approve access requests."
        
        # Create quick action buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Review Requests", callback_data="admin_access_requests")
        ]])
        
        await bot.send_message(admin_id, notification_text, reply_markup=keyboard)
        
    except Exception as e:
        logging.error(f"Failed to notify admin about access request: {e}")


@router.message(lambda message: not is_user_authorized(message.from_user.id))
async def handle_unauthorized_message(message: Message):
    """Handle any other message from unauthorized users."""
    
    user = message.from_user
    can_request = await storage.can_request_access(user.id)
    
    response_text = f"🔒 Hello {user.first_name or 'there'}!\n\n"
    response_text += "This is a private AI assistant bot.\n\n"
    
    if can_request:
        response_text += (
            "📝 To request access, use the /request command or click the button below.\n\n"
            "⏰ You can make one access request per day."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔓 Request Access", callback_data="request_access")
        ]])
    else:
        response_text += (
            "⏳ You have already submitted an access request today.\n\n"
            "Please wait for the administrator to review your request."
        )
        keyboard = None
    
    await message.answer(response_text, reply_markup=keyboard)