import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.client.default import DefaultBotProperties

from bot.config import Config
from bot.handlers import admin, user
from bot.services.storage import Storage
from bot.keyboards import reply as kb
from bot.utils.polling import PollingMiddleware

async def on_startup(bot: Bot, storage: Storage):
    """Initialize bot on startup"""
    try:
        all_users = await storage.get_all_users()
        for user_id, _ in all_users:
            try:
                # Get user settings to check preferences
                settings = await storage.get_user_settings(user_id)
                is_admin = str(user_id) == config.admin_id
                
                # Try to restore keyboard by editing last message
                messages = await bot.get_chat_history(user_id, limit=10)
                for msg in messages:
                    if msg.from_user.is_bot and msg.reply_markup:
                        keyboard = kb.get_main_menu(is_admin=is_admin) if settings and settings.get('current_provider') else kb.get_provider_menu()
                        try:
                            await msg.edit_reply_markup(reply_markup=keyboard)
                            break
                        except Exception:
                            continue
            except Exception as e:
                logging.debug(f"Could not restore keyboard for user {user_id}: {e}")
    except Exception as e:
        logging.error(f"Error during startup keyboard restoration: {e}")

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Load config
    global config
    config = Config.from_env()
    
    # Debug print config
    print("\nBot Configuration:")
    print(f"Admin ID: {config.admin_id}")
    print(f"Allowed Users: {config.allowed_user_ids}")
    
    # Initialize storages
    memory_storage = MemoryStorage()  # For FSM
    settings_storage = Storage("data/chat.db")
    await settings_storage.ensure_initialized()  # Initialize the database
    
    # Initialize bot with new syntax
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )
    
    # Initialize dispatcher
    dp = Dispatcher(storage=memory_storage)
    
    # Register middlewares
    dp.message.middleware(ChatActionMiddleware())
    
    # Add polling middleware for rate limit handling
    dp.update.outer_middleware(PollingMiddleware(config.polling_settings))
    
    # Register routers
    dp.include_router(admin.router)  # Admin router first
    dp.include_router(user.router)   # User router second
    
    # Start polling with debug info
    print("\n[INFO] Bot is starting...")
    print("[INFO] Access Control:")
    print(f"- Admin ID: {config.admin_id}")
    print(f"- Allowed Users: {len(config.allowed_user_ids)} users")
    print("\n[INFO] Polling Configuration:")
    print(f"- Timeout: {config.polling_settings['timeout']} seconds")
    print(f"- Interval: {config.polling_settings['poll_interval']} seconds")
    print(f"- Max Backoff: {config.polling_settings['backoff']['max_delay']} seconds")
    
    # Initialize bot on startup
    await on_startup(bot, settings_storage)
    
    # Start polling with configured settings
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        polling_timeout=config.polling_settings["timeout"],
        polling_interval=config.polling_settings["poll_interval"]
    )

if __name__ == "__main__":
    asyncio.run(main())
