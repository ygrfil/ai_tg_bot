from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from ..services.storage import Storage
from ..config import Config
from ..keyboards import reply as kb
from ..handlers.user import UserStates
import aiosqlite
import logging
import traceback
from datetime import datetime
import json
import os
from typing import Dict, Any, List, Optional

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
        
    # Get time period from state or default to 30 days
    user_data = await state.get_data()
    time_period = user_data.get("stats_period", "30")  # Default to 30 days
    
    await show_stats(message, time_period, state)

async def show_stats(message: Message, time_period: str = "30", state: FSMContext = None):
    """Show statistics with the specified time period"""
    try:
        # Convert time period to days for database query
        days_map = {
            "1": "1 day",
            "7": "7 days",
            "30": "30 days",
            "90": "90 days",
            "all": "all time"
        }
        
        db_period = f"-{time_period} day" if time_period != "all" else None
        period_display = days_map.get(time_period, "30 days")
        
        async with aiosqlite.connect(storage.db_path) as db:
            # Get total users
            async with db.execute("""
                SELECT COUNT(*) as total 
                FROM users
            """) as cursor:
                total_users = (await cursor.fetchone())[0]
            
            # Get active users (24h)
            async with db.execute("""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM users 
                WHERE datetime(last_activity) > datetime('now', '-1 day')
            """) as cursor:
                active_users_24h = (await cursor.fetchone())[0]
                
            # Get active users (7d)
            async with db.execute("""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM users 
                WHERE datetime(last_activity) > datetime('now', '-7 day')
            """) as cursor:
                active_users_7d = (await cursor.fetchone())[0]

            # Get provider usage stats for the selected period
            provider_query = """
                SELECT 
                    provider,
                    COUNT(DISTINCT user_id) as unique_users,
                    SUM(message_count) as total_messages,
                    SUM(token_count) as total_tokens,
                    SUM(image_count) as total_images
                FROM usage_stats 
            """
            
            if db_period:
                provider_query += f"WHERE datetime(timestamp) > datetime('now', '{db_period}')"
                
            provider_query += " GROUP BY provider ORDER BY total_messages DESC"
            
            async with db.execute(provider_query) as cursor:
                provider_stats = await cursor.fetchall()

            # Get top users for the selected period
            users_query = """
                SELECT 
                    u.user_id,
                    u.username,
                    u.first_name,
                    SUM(us.message_count) as total_messages,
                    SUM(us.token_count) as total_tokens,
                    SUM(us.image_count) as total_images,
                    GROUP_CONCAT(DISTINCT us.provider) as providers
                FROM users u
                JOIN usage_stats us ON u.user_id = us.user_id
            """
            
            if db_period:
                users_query += f"WHERE datetime(us.timestamp) > datetime('now', '{db_period}')"
                
            users_query += """
                GROUP BY u.user_id, u.username, u.first_name
                ORDER BY total_messages DESC
                LIMIT 5
            """
            
            async with db.execute(users_query) as cursor:
                top_users = await cursor.fetchall()
                
            # Get daily activity for chart data (last 7 days)
            async with db.execute("""
                SELECT 
                    date(timestamp) as day,
                    COUNT(DISTINCT user_id) as active_users,
                    SUM(message_count) as messages
                FROM usage_stats
                WHERE datetime(timestamp) > datetime('now', '-7 day')
                GROUP BY day
                ORDER BY day ASC
            """) as cursor:
                daily_activity = await cursor.fetchall()
                
            # Get model usage breakdown
            model_query = """
                SELECT 
                    model,
                    COUNT(DISTINCT user_id) as unique_users,
                    SUM(message_count) as total_messages,
                    SUM(token_count) as total_tokens
                FROM usage_stats
            """
            
            if db_period:
                model_query += f" WHERE datetime(timestamp) > datetime('now', '{db_period}')"
                
            model_query += " GROUP BY model ORDER BY total_messages DESC"
            
            async with db.execute(model_query) as cursor:
                model_stats = await cursor.fetchall()
                
            # Get user-model breakdown (which users use which models)
            user_model_query = """
                SELECT 
                    u.user_id,
                    u.username,
                    u.first_name,
                    us.provider,
                    us.model,
                    COUNT(*) as usage_count,
                    MAX(us.timestamp) as last_used
                FROM users u
                JOIN usage_stats us ON u.user_id = us.user_id
            """
            
            if db_period:
                user_model_query += f" WHERE datetime(us.timestamp) > datetime('now', '{db_period}')"
                
            user_model_query += """
                GROUP BY u.user_id, us.model
                ORDER BY u.user_id, usage_count DESC
            """
            
            async with db.execute(user_model_query) as cursor:
                user_model_stats = await cursor.fetchall()

        # Create period selection keyboard
        period_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="24h", callback_data="stats_period:1"),
                InlineKeyboardButton(text="7d", callback_data="stats_period:7"),
                InlineKeyboardButton(text="30d", callback_data="stats_period:30"),
                InlineKeyboardButton(text="90d", callback_data="stats_period:90"),
                InlineKeyboardButton(text="All", callback_data="stats_period:all")
            ],
            [
                InlineKeyboardButton(text="User Models", callback_data="stats_view:user_models"),
                InlineKeyboardButton(text="Overview", callback_data="stats_view:overview")
            ]
        ])

        # Format the response with emojis and better organization
        response = [
            f"<b>📊 Bot Statistics</b> ({period_display})\n",
            f"<b>👥 Users</b>",
            f"├ Total: {total_users:,}",
            f"├ Active (24h): {active_users_24h:,}",
            f"└ Active (7d): {active_users_7d:,}"
        ]

        # Add daily activity chart (text-based)
        if daily_activity:
            response.append("\n<b>📈 Daily Activity (7 days)</b>")
            
            # Find max values for scaling
            max_users = max([day[1] for day in daily_activity] or [1])
            max_msgs = max([day[2] for day in daily_activity] or [1])
            
            for day, users, msgs in daily_activity:
                # Create simple bar charts using blocks
                user_bar = "█" * int((users / max_users) * 10)
                msg_bar = "█" * int((msgs / max_msgs) * 10)
                
                day_fmt = datetime.strptime(day, "%Y-%m-%d").strftime("%d %b")
                response.append(f"{day_fmt}: {users} users {user_bar} | {msgs:,} msgs {msg_bar}")

        # Add provider stats
        if provider_stats:
            response.append("\n<b>🤖 Provider Usage</b>")
            
            # Calculate totals for percentage
            total_messages = sum([p[2] for p in provider_stats]) or 1
            total_tokens = sum([p[3] for p in provider_stats]) or 1
            
            for provider, users, messages, tokens, images in provider_stats:
                provider_name = provider.capitalize() if provider else 'Unknown'
                msg_percent = (messages / total_messages) * 100
                token_percent = (tokens / total_tokens) * 100
                
                response.append(
                    f"\n<b>{provider_name}</b>\n"
                    f"├ Users: {users:,}\n"
                    f"├ Messages: {messages:,} ({msg_percent:.1f}%)\n"
                    f"├ Tokens: {tokens:,} ({token_percent:.1f}%)\n"
                    f"└ Images: {images:,}"
                )
        else:
            response.append("\n<i>No provider usage data available</i>")
            
        # Add model stats
        if model_stats:
            response.append("\n<b>📱 Model Usage</b>")
            
            # Calculate totals for percentage
            total_model_messages = sum([m[2] for m in model_stats]) or 1
            
            for model, users, messages, tokens in model_stats:
                model_name = model.split('/')[-1] if '/' in model else model
                msg_percent = (messages / total_model_messages) * 100
                
                response.append(
                    f"\n<b>{model_name}</b>\n"
                    f"├ Users: {users:,}\n"
                    f"├ Messages: {messages:,} ({msg_percent:.1f}%)\n"
                    f"└ Tokens: {tokens:,}"
                )

        # Add top users
        if top_users:
            response.append("\n<b>🏆 Top Users</b>")
            for i, (user_id, username, first_name, messages, tokens, images, providers) in enumerate(top_users, 1):
                # Format user display name more directly
                name_parts = []
                if first_name:
                    name_parts.append(first_name)
                if username:
                    name_parts.append(f"@{username}")
                    
                # Use a nicer display format
                display_name = " | ".join(name_parts) if name_parts else "User"
                
                # Process providers list
                providers_list = providers.split(',') if providers else []
                
                # Add medal emoji for top 3
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                
                response.append(
                    f"\n{medal} <b>{display_name}</b> (ID: {user_id})\n"
                    f"├ Messages: {messages:,}\n"
                    f"├ Tokens: {tokens:,}\n"
                    f"├ Images: {images:,}\n"
                    f"└ Models: {', '.join(p.capitalize() for p in providers_list)}"
                )

        # Store user model stats in state for the detailed view
        if state:
            user_data = await state.get_data()
            user_data["user_model_stats"] = user_model_stats
            await state.update_data(user_data)

        await message.answer(
            "\n".join(response),
            parse_mode="HTML",
            reply_markup=period_keyboard
        )

    except Exception as e:
        logging.error(f"Error in stats command: {str(e)}")
        logging.error(traceback.format_exc())
        await message.answer(
            "❌ Error fetching statistics",
            reply_markup=kb.get_admin_menu()
        )

# Add a callback query handler for period selection
@router.callback_query(lambda c: c.data and c.data.startswith("stats_period:"))
async def process_stats_period(callback_query: CallbackQuery, state: FSMContext):
    """Process stats period selection"""
    if str(callback_query.from_user.id) != config.admin_id:
        return
    
    # Extract the period from callback data
    period = callback_query.data.split(":")[1]
    
    # Save the selected period in state
    await state.update_data(stats_period=period)
    
    # Show stats with the selected period
    await callback_query.answer(f"Showing stats for period: {period}")
    await show_stats(callback_query.message, period, state)

# Add a callback query handler for stats view selection
@router.callback_query(lambda c: c.data and c.data.startswith("stats_view:"))
async def process_stats_view(callback_query: CallbackQuery, state: FSMContext):
    """Process stats view selection"""
    if str(callback_query.from_user.id) != config.admin_id:
        return
    
    # Extract the view type from callback data
    view_type = callback_query.data.split(":")[1]
    
    if view_type == "overview":
        # Get the current period and show the overview stats
        user_data = await state.get_data()
        period = user_data.get("stats_period", "30")
        await callback_query.answer("Showing overview stats")
        await show_stats(callback_query.message, period, state)
        return
    
    if view_type == "user_models":
        await callback_query.answer("Showing user model details")
        
        # Get the user model stats from state
        user_data = await state.get_data()
        user_model_stats = user_data.get("user_model_stats", [])
        period = user_data.get("stats_period", "30")
        period_display = {
            "1": "24 hours",
            "7": "7 days",
            "30": "30 days",
            "90": "90 days",
            "all": "all time"
        }.get(period, "30 days")
        
        if not user_model_stats:
            await callback_query.message.answer(
                "No user model data available.",
                reply_markup=kb.get_admin_menu()
            )
            return
        
        # Group by user
        users = {}
        for user_id, username, first_name, provider, model, count, last_used in user_model_stats:
            if user_id not in users:
                # Format display name directly
                name_parts = []
                if first_name:
                    name_parts.append(first_name)
                if username:
                    name_parts.append(f"@{username}")
                    
                # Use a readable display format
                display_name = " | ".join(name_parts) if name_parts else "User"
                
                users[user_id] = {
                    "name": display_name,
                    "id": user_id,
                    "models": []
                }
            
            # Format the model name to be more readable
            model_name = model.split('/')[-1] if '/' in model else model
            
            # Format the last used date
            try:
                last_used_date = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                last_used_str = last_used_date.strftime("%d %b %Y %H:%M")
            except:
                last_used_str = "Unknown"
            
            users[user_id]["models"].append({
                "provider": provider,
                "model": model_name,
                "count": count,
                "last_used": last_used_str
            })
        
        # Create the response
        response = [f"<b>👤 User Model Usage</b> ({period_display})\n"]
        
        for user_id, user_data in users.items():
            response.append(f"\n<b>{user_data['name']}</b> (ID: {user_id})")
            
            # Sort models by usage count
            user_data["models"].sort(key=lambda x: x["count"], reverse=True)
            
            for i, model_data in enumerate(user_data["models"]):
                # Use different bullet points for first model vs others
                bullet = "🔹" if i == 0 else "┊"
                response.append(
                    f"{bullet} <b>{model_data['model']}</b> ({model_data['provider']})\n"
                    f"  ├ Usage: {model_data['count']} messages\n"
                    f"  └ Last used: {model_data['last_used']}"
                )
        
        # Create back button
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Back to Overview", callback_data="stats_view:overview")]
        ])
        
        # Split response if it's too long
        if len("\n".join(response)) > 4000:
            # Send first part
            await callback_query.message.answer(
                "\n".join(response[:len(response)//2]),
                parse_mode="HTML"
            )
            # Send second part with keyboard
            await callback_query.message.answer(
                "\n".join(response[len(response)//2:]),
                parse_mode="HTML",
                reply_markup=back_keyboard
            )
        else:
            await callback_query.message.answer(
                "\n".join(response),
                parse_mode="HTML",
                reply_markup=back_keyboard
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

@router.message(F.text == "👥 Users", UserStates.admin_menu)
async def users_button(message: Message, state: FSMContext):
    """Handle users button press to show user management options"""
    if str(message.from_user.id) != config.admin_id:
        return
        
    try:
        # Get user counts
        async with aiosqlite.connect(storage.db_path) as db:
            # Get total users
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
                
            # Get recent users (joined in last 7 days)
            async with db.execute("""
                SELECT COUNT(*) FROM users 
                WHERE datetime(created_at) > datetime('now', '-7 day')
            """) as cursor:
                new_users = (await cursor.fetchone())[0]
                
            # Get most recent users
            async with db.execute("""
                SELECT user_id, username, first_name, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 5
            """) as cursor:
                recent_users = await cursor.fetchall()
        
        # Create user management keyboard
        user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="View All Users", callback_data="users:view_all"),
                InlineKeyboardButton(text="Export Users", callback_data="users:export")
            ],
            [
                InlineKeyboardButton(text="Block User", callback_data="users:block"),
                InlineKeyboardButton(text="Unblock User", callback_data="users:unblock")
            ]
        ])
        
        # Format response
        response = [
            "<b>👥 User Management</b>\n",
            f"Total Users: {total_users:,}",
            f"New Users (7d): {new_users:,}"
        ]
        
        if recent_users:
            response.append("\n<b>Recently Joined Users:</b>")
            for user_id, username, first_name, created_at in recent_users:
                # Format user info
                user_parts = []
                if username:
                    user_parts.append(f"@{username}")
                if first_name:
                    user_parts.append(first_name)
                    
                user_display = " | ".join(user_parts) if user_parts else f"Unknown"
                
                # Format date
                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = date_obj.strftime("%d %b %Y")
                
                response.append(f"• <b>{user_display}</b> (ID: {user_id}) - {date_str}")
        
        await message.answer(
            "\n".join(response),
            parse_mode="HTML",
            reply_markup=user_keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in users command: {str(e)}")
        logging.error(traceback.format_exc())
        await message.answer(
            "❌ Error fetching user data",
            reply_markup=kb.get_admin_menu()
        )

@router.message(F.text == "⚙️ Settings", UserStates.admin_menu)
async def settings_button(message: Message, state: FSMContext):
    """Handle settings button press to show bot settings"""
    if str(message.from_user.id) != config.admin_id:
        return
    
    # Create settings keyboard
    settings_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Rate Limits", callback_data="settings:rate_limits"),
            InlineKeyboardButton(text="Model Settings", callback_data="settings:models")
        ],
        [
            InlineKeyboardButton(text="Database", callback_data="settings:database"),
            InlineKeyboardButton(text="Export Logs", callback_data="settings:logs")
        ],
        [
            InlineKeyboardButton(text="Verify Stats", callback_data="settings:verify_stats")
        ]
    ])
    
    # Get bot uptime
    try:
        import psutil
        import os
        from datetime import datetime
        
        process = psutil.Process(os.getpid())
        start_time = datetime.fromtimestamp(process.create_time())
        uptime = datetime.now() - start_time
        
        # Format uptime
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        # Get memory usage
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        # Get CPU usage
        cpu_percent = process.cpu_percent(interval=0.1)
    except ImportError:
        uptime_str = "N/A"
        memory_mb = 0
        cpu_percent = 0
    except Exception as e:
        logging.error(f"Error getting system stats: {e}")
        uptime_str = "Error"
        memory_mb = 0
        cpu_percent = 0
    
    response = [
        "<b>⚙️ Bot Settings</b>\n",
        f"<b>System Status:</b>",
        f"├ Uptime: {uptime_str}",
        f"├ Memory: {memory_mb:.1f} MB",
        f"└ CPU: {cpu_percent:.1f}%\n",
        f"<b>Configuration:</b>",
        f"├ Admin ID: {config.admin_id}",
        f"├ Allowed Users: {len(config.allowed_user_ids)} users",
        f"└ Polling Interval: {config.polling_settings.get('poll_interval', 'N/A')}s"
    ]
    
    await message.answer(
        "\n".join(response),
        parse_mode="HTML",
        reply_markup=settings_keyboard
    )

# Add callback handlers for user management
@router.callback_query(lambda c: c.data and c.data.startswith("users:"))
async def process_users_callback(callback_query: CallbackQuery, state: FSMContext):
    """Process user management callbacks"""
    if str(callback_query.from_user.id) != config.admin_id:
        return
    
    # Extract the action from callback data
    parts = callback_query.data.split(":")
    action = parts[1]
    
    if action == "view_all":
        await callback_query.answer("Fetching user list...")
        
        try:
            async with aiosqlite.connect(storage.db_path) as db:
                async with db.execute("""
                    SELECT user_id, username, first_name, last_activity
                    FROM users
                    ORDER BY last_activity DESC
                    LIMIT 20
                """) as cursor:
                    users = await cursor.fetchall()
            
            if not users:
                await callback_query.message.answer("No users found.")
                return
                
            response = ["<b>👥 User List</b> (Most recently active)\n"]
            
            for user_id, username, first_name, last_activity in users:
                # Format display name directly
                name_parts = []
                if first_name:
                    name_parts.append(first_name)
                if username:
                    name_parts.append(f"@{username}")
                    
                # Use a readable display format
                display_name = " | ".join(name_parts) if name_parts else "User"
                
                # Format last activity
                try:
                    last_active = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                    last_active_str = last_active.strftime("%d %b %Y %H:%M")
                except:
                    last_active_str = "Unknown"
                
                response.append(f"• <b>{display_name}</b>\n  ID: {user_id} | Last active: {last_active_str}")
                
                # Add view details button for each user
                response.append(f"  <a href=\"tg://user?id={user_id}\">Open Chat</a> | <a href=\"#\" data-user-id=\"{user_id}\">View Details</a>")
            
            # Add pagination buttons
            pagination_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="◀️ Previous", callback_data="users:prev_page"),
                    InlineKeyboardButton(text="Next ▶️", callback_data="users:next_page")
                ],
                [InlineKeyboardButton(text="Back to User Management", callback_data="users:back")]
            ])
            
            # Add user detail buttons
            user_buttons = []
            for user_id, _, _, _ in users:
                user_buttons.append([
                    InlineKeyboardButton(text=f"User {user_id} Details", callback_data=f"users:details:{user_id}")
                ])
            
            # Combine keyboards
            combined_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                *user_buttons,
                *pagination_keyboard.inline_keyboard
            ])
            
            await callback_query.message.answer(
                "\n".join(response),
                parse_mode="HTML",
                reply_markup=combined_keyboard
            )
            
        except Exception as e:
            logging.error(f"Error fetching user list: {e}")
            await callback_query.message.answer(f"Error fetching user list: {str(e)}")
    
    elif action == "export":
        await callback_query.answer("Exporting user data...")
        # This would be implemented to export user data to CSV
        await callback_query.message.answer("User export feature coming soon!")
    
    elif action == "back":
        await callback_query.answer()
        await users_button(callback_query.message, state)
    
    elif action == "details":
        # Extract user ID from callback data
        if len(parts) >= 3:
            user_id = parts[2]
            await callback_query.answer(f"Fetching details for user {user_id}")
            await show_user_details(callback_query.message, user_id, state)
        else:
            await callback_query.answer("Invalid user ID")
    
    else:
        await callback_query.answer(f"Action '{action}' not implemented yet")

async def show_user_details(message: Message, user_id: str, state: FSMContext):
    """Show detailed information about a specific user"""
    try:
        async with aiosqlite.connect(storage.db_path) as db:
            # Get user info
            async with db.execute("""
                SELECT user_id, username, first_name, last_activity, created_at, current_provider, current_model
                FROM users
                WHERE user_id = ?
            """, (user_id,)) as cursor:
                user_info = await cursor.fetchone()
                
            if not user_info:
                await message.answer(f"User {user_id} not found.")
                return
                
            # Get user's model usage
            async with db.execute("""
                SELECT 
                    provider,
                    model,
                    COUNT(*) as usage_count,
                    SUM(token_count) as total_tokens,
                    SUM(image_count) as total_images,
                    MAX(timestamp) as last_used
                FROM usage_stats
                WHERE user_id = ?
                GROUP BY provider, model
                ORDER BY usage_count DESC
            """, (user_id,)) as cursor:
                model_usage = await cursor.fetchall()
                
            # Get user's recent activity
            async with db.execute("""
                SELECT 
                    provider,
                    model,
                    message_count,
                    token_count,
                    image_count,
                    timestamp
                FROM usage_stats
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
            """, (user_id,)) as cursor:
                recent_activity = await cursor.fetchall()
                
            # Get total usage stats
            async with db.execute("""
                SELECT 
                    COUNT(*) as total_messages,
                    SUM(token_count) as total_tokens,
                    SUM(image_count) as total_images
                FROM usage_stats
                WHERE user_id = ?
            """, (user_id,)) as cursor:
                total_stats = await cursor.fetchone()
        
        # Format user info
        user_id, username, first_name, last_activity, created_at, current_provider, current_model = user_info
        
        # Format display name directly
        name_parts = []
        if first_name:
            name_parts.append(first_name)
        if username:
            name_parts.append(f"@{username}")
            
        # Use a readable display format
        display_name = " | ".join(name_parts) if name_parts else "User"
        
        # Format dates
        try:
            last_active = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            last_active_str = last_active.strftime("%d %b %Y %H:%M")
        except:
            last_active_str = "Unknown"
            
        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            created_str = created.strftime("%d %b %Y %H:%M")
        except:
            created_str = "Unknown"
        
        # Format response
        response = [
            f"<b>👤 User Details</b>\n",
            f"<b>{display_name}</b> (ID: {user_id})",
            f"├ Joined: {created_str}",
            f"├ Last Active: {last_active_str}",
            f"└ Current Model: {current_model or 'None'} ({current_provider or 'None'})"
        ]
        
        # Add total stats
        if total_stats:
            total_messages, total_tokens, total_images = total_stats
            response.append(f"\n<b>📊 Usage Statistics</b>")
            response.append(f"├ Total Messages: {total_messages or 0:,}")
            response.append(f"├ Total Tokens: {total_tokens or 0:,}")
            response.append(f"└ Total Images: {total_images or 0:,}")
        
        # Add model usage
        if model_usage:
            response.append(f"\n<b>🤖 Model Preferences</b>")
            for provider, model, count, tokens, images, last_used in model_usage:
                # Format model name
                model_name = model.split('/')[-1] if '/' in model else model
                
                # Format last used date
                try:
                    last_used_date = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                    last_used_str = last_used_date.strftime("%d %b %Y %H:%M")
                except:
                    last_used_str = "Unknown"
                
                response.append(
                    f"\n<b>{model_name}</b> ({provider})\n"
                    f"├ Usage: {count:,} messages\n"
                    f"├ Tokens: {tokens or 0:,}\n"
                    f"├ Images: {images or 0:,}\n"
                    f"└ Last Used: {last_used_str}"
                )
        
        # Add recent activity
        if recent_activity:
            response.append(f"\n<b>🕒 Recent Activity</b>")
            for provider, model, msg_count, token_count, image_count, timestamp in recent_activity:
                # Format model name
                model_name = model.split('/')[-1] if '/' in model else model
                
                # Format timestamp
                try:
                    ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    ts_str = ts.strftime("%d %b %Y %H:%M")
                except:
                    ts_str = "Unknown"
                
                response.append(
                    f"• {ts_str}: {model_name} ({provider})\n"
                    f"  Messages: {msg_count}, Tokens: {token_count or 0}, Images: {image_count or 0}"
                )
        
        # Create back button
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Back to User List", callback_data="users:view_all"),
                InlineKeyboardButton(text="Open Chat", url=f"tg://user?id={user_id}")
            ]
        ])
        
        await message.answer(
            "\n".join(response),
            parse_mode="HTML",
            reply_markup=back_keyboard
        )
        
    except Exception as e:
        logging.error(f"Error showing user details: {e}")
        logging.error(traceback.format_exc())
        await message.answer(f"Error showing user details: {str(e)}")

# Add callback handlers for settings
@router.callback_query(lambda c: c.data and c.data.startswith("settings:"))
async def process_settings_callback(callback_query: CallbackQuery, state: FSMContext):
    """Process settings callbacks"""
    if str(callback_query.from_user.id) != config.admin_id:
        return
    
    action = callback_query.data.split(":")[1]
    
    if action == "database":
        await callback_query.answer("Fetching database stats...")
        
        try:
            # Get database file size
            import os
            db_size = os.path.getsize(storage.db_path) / (1024 * 1024)  # Size in MB
            
            # Get table counts
            async with aiosqlite.connect(storage.db_path) as db:
                tables = {}
                for table in ["users", "chat_history", "usage_stats"]:
                    async with db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                        tables[table] = (await cursor.fetchone())[0]
            
            response = [
                "<b>🗄️ Database Information</b>\n",
                f"Database Size: {db_size:.2f} MB\n",
                "<b>Table Records:</b>",
                f"├ Users: {tables.get('users', 0):,}",
                f"├ Chat History: {tables.get('chat_history', 0):,}",
                f"└ Usage Stats: {tables.get('usage_stats', 0):,}"
            ]
            
            # Add maintenance buttons
            maintenance_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Optimize DB", callback_data="settings:optimize_db"),
                    InlineKeyboardButton(text="Backup DB", callback_data="settings:backup_db")
                ],
                [InlineKeyboardButton(text="Back to Settings", callback_data="settings:back")]
            ])
            
            await callback_query.message.answer(
                "\n".join(response),
                parse_mode="HTML",
                reply_markup=maintenance_keyboard
            )
            
        except Exception as e:
            logging.error(f"Error fetching database stats: {e}")
            await callback_query.message.answer(f"Error fetching database stats: {str(e)}")
    
    elif action == "verify_stats":
        await callback_query.answer("Verifying usage statistics...")
        
        try:
            # Check if usage_stats table exists and has data
            async with aiosqlite.connect(storage.db_path) as db:
                # Check table structure
                async with db.execute("PRAGMA table_info(usage_stats)") as cursor:
                    columns = await cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                # Check for recent entries
                async with db.execute("""
                    SELECT COUNT(*) FROM usage_stats 
                    WHERE datetime(timestamp) > datetime('now', '-1 day')
                """) as cursor:
                    recent_entries = (await cursor.fetchone())[0]
                
                # Check user data storage
                async with db.execute("""
                    SELECT user_id, username, first_name, last_activity
                    FROM users 
                    ORDER BY last_activity DESC
                    LIMIT 5
                """) as cursor:
                    user_data = await cursor.fetchall()
                    
                # Get sample data with user info
                async with db.execute("""
                    SELECT us.user_id, u.username, u.first_name, us.provider, us.model, 
                           us.message_count, us.token_count, us.image_count, us.timestamp
                    FROM usage_stats us
                    JOIN users u ON us.user_id = u.user_id
                    ORDER BY us.timestamp DESC
                    LIMIT 5
                """) as cursor:
                    sample_data = await cursor.fetchall()
            
            response = [
                "<b>📊 Usage Stats Verification</b>\n",
                f"<b>Table Structure:</b> {'✅ OK' if len(column_names) >= 7 else '❌ Missing columns'}",
                f"<b>Required Columns:</b> {', '.join(column_names)}",
                f"<b>Recent Entries (24h):</b> {recent_entries}"
            ]
            
            # Add user data storage check
            if user_data:
                response.append("\n<b>User Data Storage:</b>")
                for user_id, username, first_name, last_activity in user_data:
                    name_parts = []
                    if first_name:
                        name_parts.append(first_name)
                    if username:
                        name_parts.append(f"@{username}")
                    
                    display_name = " | ".join(name_parts) if name_parts else "<No name saved>"
                    
                    response.append(
                        f"• User ID: {user_id}\n"
                        f"  ├ Stored name: {display_name}\n"
                        f"  ├ Username value: {username or '<empty>'}\n"
                        f"  ├ First name value: {first_name or '<empty>'}\n"
                        f"  └ Last active: {last_activity}"
                    )
                    
                response.append("\n<b>How usernames are saved:</b>")
                response.append("1. When users send messages to the bot, their username and first_name are automatically saved.")
                response.append("2. Names can also be detected from conversations (e.g., 'Hello John' or 'My name is Jane').")
                response.append("3. If a user has an empty username, you can use 'Update Username' to test.")
                response.append("4. For best results, users should send at least one message to the bot.")
            else:
                response.append("\n❌ No user data found in database.")
            
            if sample_data:
                response.append("\n<b>Recent Usage Data:</b>")
                for user_id, username, first_name, provider, model, msg_count, token_count, img_count, timestamp in sample_data:
                    # Format display name directly
                    name_parts = []
                    if first_name:
                        name_parts.append(first_name)
                    if username:
                        name_parts.append(f"@{username}")
                    
                    display_name = " | ".join(name_parts) if name_parts else f"User {user_id}"
                    
                    # Format timestamp
                    try:
                        ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        ts_str = ts.strftime("%d %b %Y %H:%M")
                    except:
                        ts_str = timestamp
                        
                    response.append(
                        f"• <b>{display_name}</b> (ID: {user_id})\n"
                        f"  ├ Provider: {provider}\n"
                        f"  ├ Model: {model}\n"
                        f"  ├ Messages: {msg_count}, Tokens: {token_count}, Images: {img_count}\n"
                        f"  └ Time: {ts_str}"
                    )
            else:
                response.append("\n❌ No usage data found. Stats may not be recording correctly.")
                response.append("\nTry sending a message to the bot to generate usage data.")
            
            # Add action buttons
            action_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Test Log Entry", callback_data="settings:test_log"),
                    InlineKeyboardButton(text="Update Username", callback_data="settings:update_username")
                ],
                [InlineKeyboardButton(text="Back", callback_data="settings:back")]
            ])
            
            await callback_query.message.answer(
                "\n".join(response),
                parse_mode="HTML",
                reply_markup=action_keyboard
            )
            
        except Exception as e:
            logging.error(f"Error verifying stats: {e}")
            await callback_query.message.answer(f"Error verifying stats: {str(e)}")
    
    elif action == "test_log":
        await callback_query.answer("Creating test log entry...")
        
        try:
            # Create a test log entry
            await storage.log_usage(
                user_id=int(config.admin_id),
                provider="test",
                model="test_model",
                tokens=100,
                has_image=False
            )
            
            await callback_query.message.answer(
                "✅ Test log entry created successfully!\n\n"
                "You can now check the stats to verify it's working.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="View Stats", callback_data="stats_period:1")],
                    [InlineKeyboardButton(text="Back to Settings", callback_data="settings:back")]
                ])
            )
            
        except Exception as e:
            logging.error(f"Error creating test log: {e}")
            await callback_query.message.answer(f"Error creating test log: {str(e)}")
    
    elif action == "update_username":
        await callback_query.answer("Testing username update...")
        
        try:
            # Get user ID and update their username and first name for testing
            user_id = int(config.admin_id)
            
            async with aiosqlite.connect(storage.db_path) as db:
                # First check if the admin already has a username set
                async with db.execute("""
                    SELECT username, first_name FROM users
                    WHERE user_id = ?
                """, (user_id,)) as cursor:
                    current_data = await cursor.fetchone()
                
                # Toggle the username and first name for testing
                new_username = None if current_data and current_data[0] else "admin_test"
                new_first_name = None if current_data and current_data[1] else "Admin User"
                
                # Update the admin's username and first name
                await db.execute("""
                    UPDATE users
                    SET username = ?, first_name = ?
                    WHERE user_id = ?
                """, (new_username, new_first_name, user_id))
                await db.commit()
            
            status = "cleared" if new_username is None else "set"
            
            await callback_query.message.answer(
                f"✅ Username and first name {status} for testing!\n\n"
                f"Admin user now has:\n"
                f"- Username: {new_username or '<empty>'}\n"
                f"- First name: {new_first_name or '<empty>'}\n\n"
                f"Check the verification again to see if it appears correctly.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Verify Again", callback_data="settings:verify_stats")],
                    [InlineKeyboardButton(text="Back", callback_data="settings:back")]
                ])
            )
            
        except Exception as e:
            logging.error(f"Error updating username: {e}")
            await callback_query.message.answer(f"Error updating username: {str(e)}")
    
    elif action == "back":
        await callback_query.answer()
        await settings_button(callback_query.message, state)
    
    else:
        await callback_query.answer(f"Action '{action}' not implemented yet")

@router.message(F.text == "🔓 Access Requests", UserStates.admin_menu)
async def access_requests_button(message: Message, state: FSMContext):
    """Handle access requests button press to show access request management"""
    if str(message.from_user.id) != config.admin_id:
        return
        
    try:
        # Get access request stats
        stats = await storage.get_access_request_stats()
        pending_requests = await storage.get_pending_access_requests()
        
        # Create access request management keyboard
        request_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"🔍 Review ({stats['pending']})", callback_data="access:review"),
                InlineKeyboardButton(text="📋 All Requests", callback_data="access:all")
            ],
            [
                InlineKeyboardButton(text="👤 Add User", callback_data="access:add_user"),
                InlineKeyboardButton(text="🚫 Remove User", callback_data="access:remove_user")
            ],
            [
                InlineKeyboardButton(text="📊 Statistics", callback_data="access:stats")
            ]
        ])
        
        # Format response
        response = [
            "<b>🔓 Access Request Management</b>\n",
            f"📬 Pending Requests: <b>{stats['pending']}</b>",
            f"📅 Requests Today: {stats['today']}",
            f"✅ Approved This Week: {stats['approved_this_week']}"
        ]
        
        if pending_requests:
            response.append("\n<b>⏰ Recent Pending Requests:</b>")
            for req in pending_requests[:3]:  # Show only first 3
                # Format user info
                name_parts = []
                if req['first_name']:
                    name_parts.append(req['first_name'])
                if req['last_name']:
                    name_parts.append(req['last_name'])
                if req['username']:
                    name_parts.append(f"@{req['username']}")
                    
                display_name = " | ".join(name_parts) if name_parts else f"User {req['user_id']}"
                
                # Format timestamp
                try:
                    ts = datetime.fromisoformat(req['request_timestamp'].replace('Z', '+00:00'))
                    ts_str = ts.strftime("%d %b %Y %H:%M")
                except:
                    ts_str = "Unknown"
                
                # Truncate message if too long
                message_preview = req['request_message']
                if message_preview and len(message_preview) > 100:
                    message_preview = message_preview[:100] + "..."
                
                response.append(f"• <b>{display_name}</b> (ID: {req['user_id']})")
                response.append(f"  ├ Time: {ts_str}")
                response.append(f"  └ Message: {message_preview or 'No message'}")
        else:
            response.append("\n✨ No pending requests")
        
        await message.answer(
            "\n".join(response),
            parse_mode="HTML",
            reply_markup=request_keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in access requests command: {str(e)}")
        logging.error(traceback.format_exc())
        await message.answer(
            "❌ Error fetching access request data",
            reply_markup=kb.get_admin_menu()
        )

# Add callback handlers for access request management
@router.callback_query(lambda c: c.data and c.data.startswith("access:"))
async def process_access_callback(callback_query: CallbackQuery, state: FSMContext):
    """Process access request management callbacks"""
    if str(callback_query.from_user.id) != config.admin_id:
        return
    
    # Extract the action from callback data
    parts = callback_query.data.split(":")
    action = parts[1]
    
    if action == "review":
        await callback_query.answer("Loading pending requests...")
        
        try:
            pending_requests = await storage.get_pending_access_requests()
            
            if not pending_requests:
                await callback_query.message.answer(
                    "✨ No pending access requests!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Back", callback_data="access:back")]
                    ])
                )
                return
            
            # Show each request with approve/reject buttons
            for req in pending_requests:
                # Format user info
                name_parts = []
                if req['first_name']:
                    name_parts.append(req['first_name'])
                if req['last_name']:
                    name_parts.append(req['last_name'])
                if req['username']:
                    name_parts.append(f"@{req['username']}")
                    
                display_name = " | ".join(name_parts) if name_parts else f"User {req['user_id']}"
                
                # Format timestamp
                try:
                    ts = datetime.fromisoformat(req['request_timestamp'].replace('Z', '+00:00'))
                    ts_str = ts.strftime("%d %b %Y %H:%M")
                except:
                    ts_str = "Unknown"
                
                response = [
                    f"<b>🔍 Access Request #{req['id']}</b>\n",
                    f"👤 <b>User:</b> {display_name}",
                    f"🆔 <b>ID:</b> <code>{req['user_id']}</code>",
                    f"⏰ <b>Requested:</b> {ts_str}",
                    f"\n💬 <b>Message:</b>\n{req['request_message'] or 'No message provided'}"
                ]
                
                # Create approve/reject buttons
                decision_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Approve", callback_data=f"access:approve:{req['id']}"),
                        InlineKeyboardButton(text="❌ Reject", callback_data=f"access:reject:{req['id']}")
                    ],
                    [
                        InlineKeyboardButton(text="📝 View Details", callback_data=f"access:details:{req['user_id']}")
                    ]
                ])
                
                await callback_query.message.answer(
                    "\n".join(response),
                    parse_mode="HTML",
                    reply_markup=decision_keyboard
                )
            
            # Add navigation button
            await callback_query.message.answer(
                f"<b>📋 All {len(pending_requests)} pending requests shown above.</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Back to Access Management", callback_data="access:back")]
                ])
            )
            
        except Exception as e:
            logging.error(f"Error loading pending requests: {e}")
            await callback_query.message.answer(f"Error loading requests: {str(e)}")
    
    elif action == "approve":
        if len(parts) >= 3:
            request_id = int(parts[2])
            await callback_query.answer("Approving access request...")
            
            try:
                success = await storage.approve_access_request(request_id, int(config.admin_id))
                
                if success:
                    # Get request details for notification
                    async with aiosqlite.connect(storage.db_path) as db:
                        async with db.execute("""
                            SELECT user_id, username, first_name FROM access_requests 
                            WHERE id = ?
                        """, (request_id,)) as cursor:
                            req_data = await cursor.fetchone()
                    
                    if req_data:
                        user_id, username, first_name = req_data
                        
                        # Update allowed users list in config
                        if str(user_id) not in config.allowed_user_ids:
                            config.allowed_user_ids.append(str(user_id))
                            
                            # Try to update .env file
                            try:
                                import os
                                from pathlib import Path
                                
                                env_path = Path(".env")
                                if env_path.exists():
                                    # Read current .env content
                                    with open(env_path, "r") as f:
                                        lines = f.readlines()
                                    
                                    # Update ALLOWED_USER_IDS line
                                    new_ids = ",".join(config.allowed_user_ids)
                                    updated = False
                                    for i, line in enumerate(lines):
                                        if line.startswith("ALLOWED_USER_IDS="):
                                            lines[i] = f"ALLOWED_USER_IDS={new_ids}\n"
                                            updated = True
                                            break
                                    
                                    if updated:
                                        with open(env_path, "w") as f:
                                            f.writelines(lines)
                                        logging.info(f"Updated .env file with new user: {user_id}")
                                    else:
                                        logging.warning("ALLOWED_USER_IDS not found in .env file")
                                        
                            except Exception as env_error:
                                logging.error(f"Error updating .env file: {env_error}")
                        
                        # Notify the user about approval
                        try:
                            await callback_query.bot.send_message(
                                user_id,
                                "🎉 <b>Access Approved!</b>\n\n"
                                "Your request to use this AI assistant bot has been approved.\n\n"
                                "You can now start chatting with the bot. Use /start to begin!\n\n"
                                "Welcome to the bot! 🤖",
                                parse_mode="HTML"
                            )
                        except Exception as notify_error:
                            logging.error(f"Failed to notify user {user_id} about approval: {notify_error}")
                    
                    await callback_query.message.edit_text(
                        f"✅ <b>Request #{request_id} approved successfully!</b>\n\n"
                        f"User {user_id} has been added to the allowed users list and notified.",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="Back to Requests", callback_data="access:review")]
                        ])
                    )
                else:
                    await callback_query.message.answer("❌ Failed to approve request. It may have already been processed.")
                    
            except Exception as e:
                logging.error(f"Error approving request: {e}")
                await callback_query.message.answer(f"❌ Error approving request: {str(e)}")
        else:
            await callback_query.answer("Invalid request ID")
    
    elif action == "reject":
        if len(parts) >= 3:
            request_id = int(parts[2])
            await callback_query.answer("Rejecting access request...")
            
            try:
                # Get request details before rejecting
                async with aiosqlite.connect(storage.db_path) as db:
                    async with db.execute("""
                        SELECT user_id, username, first_name FROM access_requests 
                        WHERE id = ? AND status = 'pending'
                    """, (request_id,)) as cursor:
                        req_data = await cursor.fetchone()
                
                if req_data:
                    user_id, username, first_name = req_data
                    
                    success = await storage.reject_access_request(request_id, int(config.admin_id))
                    
                    if success:
                        # Notify the user about rejection
                        try:
                            await callback_query.bot.send_message(
                                user_id,
                                "❌ <b>Access Request Declined</b>\n\n"
                                "Unfortunately, your request to use this AI assistant bot has been declined.\n\n"
                                "You can submit a new request tomorrow if you'd like to try again.\n\n"
                                "Thank you for your understanding.",
                                parse_mode="HTML"
                            )
                        except Exception as notify_error:
                            logging.error(f"Failed to notify user {user_id} about rejection: {notify_error}")
                        
                        await callback_query.message.edit_text(
                            f"❌ <b>Request #{request_id} rejected.</b>\n\n"
                            f"User {user_id} has been notified about the decision.",
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="Back to Requests", callback_data="access:review")]
                            ])
                        )
                    else:
                        await callback_query.message.answer("❌ Failed to reject request. It may have already been processed.")
                else:
                    await callback_query.message.answer("❌ Request not found or already processed.")
                    
            except Exception as e:
                logging.error(f"Error rejecting request: {e}")
                await callback_query.message.answer(f"❌ Error rejecting request: {str(e)}")
        else:
            await callback_query.answer("Invalid request ID")
    
    elif action == "stats":
        await callback_query.answer("Loading access request statistics...")
        
        try:
            stats = await storage.get_access_request_stats()
            
            # Get additional detailed stats
            async with aiosqlite.connect(storage.db_path) as db:
                # Count by status
                async with db.execute("""
                    SELECT status, COUNT(*) FROM access_requests 
                    GROUP BY status
                """) as cursor:
                    status_counts = await cursor.fetchall()
                
                # Recent activity
                async with db.execute("""
                    SELECT COUNT(*) FROM access_requests 
                    WHERE request_timestamp >= date('now', '-7 days')
                """) as cursor:
                    recent_requests = (await cursor.fetchone())[0]
                
                # Top requesting users (users who made multiple requests)
                async with db.execute("""
                    SELECT user_id, username, first_name, COUNT(*) as request_count
                    FROM access_requests 
                    GROUP BY user_id
                    HAVING request_count > 1
                    ORDER BY request_count DESC
                    LIMIT 5
                """) as cursor:
                    repeat_requesters = await cursor.fetchall()
            
            response = [
                "<b>📊 Access Request Statistics</b>\n",
                f"📬 Pending: <b>{stats['pending']}</b>",
                f"📅 Today: {stats['today']}",
                f"✅ Approved This Week: {stats['approved_this_week']}",
                f"📈 Requests Last 7 Days: {recent_requests}"
            ]
            
            if status_counts:
                response.append("\n<b>📋 All Time Status Breakdown:</b>")
                for status, count in status_counts:
                    status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(status, "❓")
                    response.append(f"├ {status_emoji} {status.title()}: {count}")
            
            if repeat_requesters:
                response.append("\n<b>🔄 Multiple Request Users:</b>")
                for user_id, username, first_name, count in repeat_requesters:
                    name_parts = []
                    if first_name:
                        name_parts.append(first_name)
                    if username:
                        name_parts.append(f"@{username}")
                    
                    display_name = " | ".join(name_parts) if name_parts else f"User {user_id}"
                    response.append(f"• {display_name} ({count} requests)")
            
            back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Back", callback_data="access:back")]
            ])
            
            await callback_query.message.answer(
                "\n".join(response),
                parse_mode="HTML",
                reply_markup=back_keyboard
            )
            
        except Exception as e:
            logging.error(f"Error loading access stats: {e}")
            await callback_query.message.answer(f"Error loading statistics: {str(e)}")
    
    elif action == "back":
        await callback_query.answer()
        await access_requests_button(callback_query.message, state)
    
    else:
        await callback_query.answer(f"Action '{action}' not implemented yet")

