from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from ..services.storage import Storage
from ..config import Config
import aiosqlite

router = Router()
storage = Storage("data/chat.db")
config = Config.from_env()

@router.message(Command("admin"), F.from_user.id == config.admin_id)
async def admin_command(message: Message):
    """Handle admin command - only accessible by admin"""
    await message.answer(
        "🔐 <b>Admin Panel:</b>\n\n"
        "Available commands:\n"
        "/stats - Show bot statistics\n"
        "/broadcast <text> - Send message to all users\n"
        "/adminhelp - Show detailed help",
        parse_mode="HTML"
    )

@router.message(Command("stats"), F.from_user.id == config.admin_id)
async def stats_command(message: Message):
    """Show bot statistics to admin"""
    async with aiosqlite.connect(storage.db_path) as db:
        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM users") as cursor:
            total_users = await cursor.fetchone()
    await message.answer(f"Bot Statistics:\nTotal users: {total_users[0]}")

@router.message(Command("broadcast"), F.from_user.id == config.admin_id)
async def broadcast_command(message: Message):
    """Broadcast message to all users"""
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.answer("Please provide a message to broadcast")
        return
    
    async with aiosqlite.connect(storage.db_path) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    
    success_count = 0
    fail_count = 0
    
    await message.answer(f"Starting broadcast to {len(users)} users...")
    
    for (user_id,) in users:
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>Broadcast Message from Admin:</b>\n\n{broadcast_text}",
                parse_mode="HTML"
            )
            success_count += 1
        except Exception as e:
            fail_count += 1
            print(f"Failed to send broadcast to user {user_id}: {str(e)}")
    
    await message.answer(
        f"Broadcast completed!\n"
        f"✅ Successfully sent: {success_count}\n"
        f"❌ Failed: {fail_count}"
    )

@router.message(Command("adminhelp"), F.from_user.id == config.admin_id)
async def admin_help_command(message: Message):
    """Show admin commands help"""
    help_text = (
        "🔐 <b>Admin Commands:</b>\n\n"
        "/admin - Open admin panel\n"
        "/stats - Show bot statistics\n"
        "/broadcast <text> - Send message to all users\n"
        "/adminhelp - Show this help message"
    )
    await message.answer(help_text, parse_mode="HTML")

@router.message(F.text == "👑 Admin Panel", F.from_user.id == config.admin_id)
async def admin_panel_button(message: Message):
    await admin_command(message)

@router.message(F.text == "📊 Stats", F.from_user.id == config.admin_id)
async def stats_button(message: Message):
    await stats_command(message)

@router.message(F.text == "📢 Broadcast", F.from_user.id == config.admin_id)
async def broadcast_button(message: Message):
    await message.answer(
        "To broadcast a message, use the command:\n"
        "/broadcast <your message>\n\n"
        "Example:\n"
        "/broadcast Hello everyone! This is an important announcement."
    )
