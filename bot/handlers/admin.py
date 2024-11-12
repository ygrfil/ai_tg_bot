from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from ..services.storage import JsonStorage
from ..config import Config

router = Router()
storage = JsonStorage("ai_telegram_bot/data/user_settings.json")
config = Config.from_env()

@router.message(Command("admin"), F.from_user.id == config.admin_id)
async def admin_command(message: Message):
    """Handle admin command - only accessible by admin"""
    await message.answer("Admin panel:")

@router.message(Command("stats"), F.from_user.id == config.admin_id)
async def stats_command(message: Message):
    """Show bot statistics to admin"""
    data = storage._load_data()
    total_users = len(data)
    await message.answer(f"Bot Statistics:\nTotal users: {total_users}")

@router.message(Command("broadcast"), F.from_user.id == config.admin_id)
async def broadcast_command(message: Message):
    """Broadcast message to all users"""
    # Remove the command from the message
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.answer("Please provide a message to broadcast")
        return
    
    data = storage._load_data()
    await message.answer(f"Broadcasting message to {len(data)} users...")
