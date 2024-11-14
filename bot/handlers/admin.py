from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from ..services.storage import Storage
from ..config import Config
from ..keyboards import reply as kb
from ..handlers.user import UserStates
import aiosqlite
import logging

# Create router with name
router = Router(name='admin_router')
config = Config.from_env()
storage = Storage("data/chat.db")

# Admin handlers with explicit filters
@router.message(F.text == "👑 Admin")
async def admin_panel_button(message: Message, state: FSMContext):
    """Handle admin button press"""
    if str(message.from_user.id) != config.admin_id:
        return
        
    await state.set_state(UserStates.admin_menu)
    await message.answer(
        "🔐 <b>Admin Panel</b>\n\n"
        "Choose an option:",
        reply_markup=kb.get_admin_menu(),
        parse_mode="HTML"
    )

@router.message(F.text == "🔙 Back")
async def back_button(message: Message, state: FSMContext):
    """Handle back button press"""
    if str(message.from_user.id) != config.admin_id:
        return
        
    await state.set_state(UserStates.chatting)
    await message.answer(
        "Main Menu:",
        reply_markup=kb.get_main_menu(is_admin=True)
    )

@router.message(F.text == "📊 Stats", UserStates.admin_menu)
async def stats_button(message: Message, state: FSMContext):
    """Handle stats button press with detailed statistics"""
    if str(message.from_user.id) != config.admin_id:
        return
        
    try:
        async with aiosqlite.connect(storage.db_path) as db:
            # Step 1: Just get total users
            async with db.execute("""
                SELECT COUNT(*) as total 
                FROM users
            """) as cursor:
                total_users = (await cursor.fetchone())[0]
            
            # Step 2: Get active users (last 24h)
            async with db.execute("""
                SELECT COUNT(DISTINCT chat_history.user_id) as active_users
                FROM chat_history
                WHERE chat_history.timestamp > datetime('now', '-1 day')
            """) as cursor:
                active_users = (await cursor.fetchone())[0]

            # Step 3: Get message counts by provider
            async with db.execute("""
                SELECT 
                    users.settings->>'current_provider' as provider,
                    COUNT(DISTINCT chat_history.user_id) as unique_users,
                    COUNT(*) as total_messages
                FROM chat_history
                INNER JOIN users 
                    ON chat_history.user_id = users.user_id
                WHERE chat_history.timestamp > datetime('now', '-30 day')
                GROUP BY users.settings->>'current_provider'
            """) as cursor:
                provider_stats = await cursor.fetchall()

            # Step 4: Get top users
            async with db.execute("""
                SELECT 
                    ch.user_id,
                    u.username,
                    COUNT(*) as message_count,
                    json_extract(u.settings, '$.current_provider') as current_provider
                FROM chat_history ch
                INNER JOIN users u ON ch.user_id = u.user_id
                WHERE ch.timestamp > datetime('now', '-30 day')
                GROUP BY ch.user_id
                ORDER BY message_count DESC
                LIMIT 5
            """) as cursor:
                top_users = await cursor.fetchall()

        # Format the response
        response = [
            "<b>📊 Bot Statistics</b>\n",
            f"👥 <b>Total Users:</b> {total_users}",
            f"📱 <b>Active Users (24h):</b> {active_users}"
        ]

        # Add provider stats
        if provider_stats:
            response.append("\n<b>Provider Usage (30 days):</b>")
            for provider, users, messages in provider_stats:
                provider_name = provider.capitalize() if provider else 'Unknown'
                response.append(
                    f"\n🤖 <b>{provider_name}</b>\n"
                    f"├ Users: {users}\n"
                    f"└ Messages: {messages:,}"
                )
        else:
            response.append("\n<i>No provider usage data available</i>")

        # Add top users
        if top_users:
            response.append("\n<b>Top Users (30 days):</b>")
            for user_id, username, messages, provider in top_users:
                provider_name = provider.capitalize() if provider else 'N/A'
                username_display = f"@{username}" if username else f"ID: {user_id}"
                response.append(
                    f"\n👤 {username_display}\n"
                    f"├ Messages: {messages:,}\n"
                    f"└ Provider: {provider_name}"
                )

        await message.answer(
            "\n".join(response),
            parse_mode="HTML",
            reply_markup=kb.get_admin_menu()
        )

    except Exception as e:
        logging.error(f"Error in stats command: {str(e)}")
        # Print full error traceback for debugging
        import traceback
        logging.error(traceback.format_exc())
        await message.answer(
            "❌ Error fetching statistics",
            reply_markup=kb.get_admin_menu()
        )

@router.message(F.text == "📢 Broadcast", F.from_user.id == config.admin_id)
async def broadcast_button(message: Message):
    """Handle broadcast button press"""
    print("[DEBUG] Broadcast button pressed")
    await message.answer(
        "To broadcast a message, use the command:\n"
        "/broadcast <your message>\n\n"
        "Example:\n"
        "/broadcast Hello everyone! This is an important announcement."
    )

@router.message(Command("admin"))
async def admin_command(message: Message):
    """Handle admin command"""
    await message.answer(
        "🔐 <b>Admin Panel</b>\n\n"
        "Available commands:\n"
        "/stats - Show bot statistics\n"
        "/broadcast <text> - Send message to all users\n"
        "/adminhelp - Show detailed help",
        parse_mode="HTML"
    )

@router.message(Command("stats"))
async def stats_command(message: Message):
    """Show bot statistics to admin"""
    async with aiosqlite.connect(storage.db_path) as db:
        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM users") as cursor:
            total_users = await cursor.fetchone()
    await message.answer(f"Bot Statistics:\nTotal users: {total_users[0]}")

@router.message(Command("broadcast"))
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

@router.message(Command("adminhelp"))
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

