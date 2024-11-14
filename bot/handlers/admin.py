from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from ..services.storage import Storage
from ..config import Config
from ..keyboards import reply as kb
from ..handlers.user import UserStates
import aiosqlite
import logging
import traceback

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
            # Get total users
            async with db.execute("""
                SELECT COUNT(*) as total 
                FROM users
            """) as cursor:
                total_users = (await cursor.fetchone())[0]
            
            # Get active users (last 24h)
            async with db.execute("""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM users 
                WHERE datetime(last_activity) > datetime('now', '-1 day')
            """) as cursor:
                active_users = (await cursor.fetchone())[0]

            # Get provider usage stats (30 days)
            async with db.execute("""
                SELECT 
                    provider,
                    COUNT(DISTINCT user_id) as unique_users,
                    SUM(message_count) as total_messages,
                    SUM(token_count) as total_tokens,
                    SUM(image_count) as total_images
                FROM usage_stats 
                WHERE datetime(timestamp) > datetime('now', '-30 day')
                GROUP BY provider
            """) as cursor:
                provider_stats = await cursor.fetchall()

            # Get top users (30 days)
            async with db.execute("""
                SELECT 
                    u.user_id,
                    u.username,
                    SUM(us.message_count) as total_messages,
                    SUM(us.token_count) as total_tokens,
                    SUM(us.image_count) as total_images,
                    GROUP_CONCAT(DISTINCT us.provider) as providers
                FROM users u
                JOIN usage_stats us ON u.user_id = us.user_id
                WHERE datetime(us.timestamp) > datetime('now', '-30 day')
                GROUP BY u.user_id, u.username
                ORDER BY total_messages DESC
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
            for provider, users, messages, tokens, images in provider_stats:
                provider_name = provider.capitalize() if provider else 'Unknown'
                response.append(
                    f"\n🤖 <b>{provider_name}</b>\n"
                    f"├ Users: {users}\n"
                    f"├ Messages: {messages:,}\n"
                    f"├ Tokens: {tokens:,}\n"
                    f"└ Images: {images:,}"
                )
        else:
            response.append("\n<i>No provider usage data available</i>")

        # Add top users
        if top_users:
            response.append("\n<b>Top Users (30 days):</b>")
            for user_id, username, messages, tokens, images, providers in top_users:
                display_name = f"@{username}" if username else f"ID: {user_id}"
                providers_list = providers.split(',') if providers else []
                response.append(
                    f"\n👤 <b>{display_name}</b>\n"
                    f"├ Messages: {messages:,}\n"
                    f"├ Tokens: {tokens:,}\n"
                    f"├ Images: {images:,}\n"
                    f"└ Providers: {', '.join(p.capitalize() for p in providers_list)}"
                )

        await message.answer(
            "\n".join(response),
            parse_mode="HTML",
            reply_markup=kb.get_admin_menu()
        )

    except Exception as e:
        logging.error(f"Error in stats command: {str(e)}")
        logging.error(traceback.format_exc())
        await message.answer(
            "❌ Error fetching statistics",
            reply_markup=kb.get_admin_menu()
        )

@router.message(F.text == "📢 Broadcast")
async def broadcast_button(message: Message, state: FSMContext):
    """Handle broadcast button press"""
    if str(message.from_user.id) != config.admin_id:
        return
        
    await state.set_state(UserStates.broadcasting)
    await message.answer(
        "📢 <b>Broadcast Mode</b>\n\n"
        "Send any message (text, photo, video) to broadcast to all users.\n"
        "Use /cancel to exit broadcast mode.",
        reply_markup=kb.get_back_menu(),
        parse_mode="HTML"
    )

@router.message(UserStates.broadcasting)
async def handle_broadcast(message: Message, state: FSMContext):
    """Handle messages in broadcast state"""
    if str(message.from_user.id) != config.admin_id:
        return

    if message.text == "🔙 Back" or message.text == "/cancel":
        await state.set_state(UserStates.admin_menu)
        await message.answer(
            "Broadcast cancelled.",
            reply_markup=kb.get_admin_menu()
        )
        return

    try:
        # Validate that we have content to broadcast
        has_content = bool(
            message.text or 
            message.photo or 
            message.video or 
            message.caption
        )
        
        if not has_content:
            await message.answer(
                "❌ Cannot broadcast empty message. Please send text, photo, or video.",
                reply_markup=kb.get_back_menu()
            )
            return

        # Get all allowed users
        allowed_users = set([config.admin_id] + config.allowed_user_ids)
        success_count = 0
        fail_count = 0

        # Send status message
        status_msg = await message.answer(
            "📤 Broadcasting message...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
        )

        for user_id in allowed_users:
            try:
                if message.photo:
                    caption = message.caption or ""  # Use empty string if no caption
                    await message.bot.send_photo(
                        chat_id=user_id,
                        photo=message.photo[-1].file_id,
                        caption=f"📢 <b>Broadcast from Admin:</b>\n\n{caption}",
                        parse_mode="HTML"
                    )
                elif message.video:
                    caption = message.caption or ""  # Use empty string if no caption
                    await message.bot.send_video(
                        chat_id=user_id,
                        video=message.video.file_id,
                        caption=f"📢 <b>Broadcast from Admin:</b>\n\n{caption}",
                        parse_mode="HTML"
                    )
                elif message.text:
                    # Only send text messages if there's actual text
                    if message.text.strip():
                        await message.bot.send_message(
                            chat_id=user_id,
                            text=f"📢 <b>Broadcast from Admin:</b>\n\n{message.text}",
                            parse_mode="HTML"
                        )
                success_count += 1
            except Exception as e:
                logging.error(f"Failed to send broadcast to user {user_id}: {str(e)}")
                fail_count += 1

        # Delete status message and show results
        try:
            await status_msg.delete()
        except Exception as e:
            logging.warning(f"Failed to delete status message: {str(e)}")

        # Show results with proper keyboard
        await message.answer(
            f"✅ Broadcast completed!\n\n"
            f"📨 Sent successfully: {success_count}\n"
            f"❌ Failed: {fail_count}",
            reply_markup=kb.get_admin_menu()
        )
        
        # Return to admin menu state
        await state.set_state(UserStates.admin_menu)

    except Exception as e:
        logging.error(f"Broadcast error: {str(e)}")
        logging.error(traceback.format_exc())
        await message.answer(
            "❌ Error during broadcast operation.",
            reply_markup=kb.get_admin_menu()
        )
        await state.set_state(UserStates.admin_menu)

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

