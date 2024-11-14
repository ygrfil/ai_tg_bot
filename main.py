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

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Load config
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
    
    # Register routers
    dp.include_router(admin.router)  # Admin router first
    dp.include_router(user.router)   # User router second
    
    # Start polling with debug info
    print("\n[INFO] Bot is starting...")
    print("[INFO] Access Control:")
    print(f"- Admin ID: {config.admin_id}")
    print(f"- Allowed Users: {len(config.allowed_user_ids)} users")
    
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

async def cleanup_task(storage: Storage):
    """Periodic task to clean up chat history for inactive users"""
    while True:
        try:
            await storage.cleanup_inactive_users()
            await asyncio.sleep(15 * 60)  # Run every 15 minutes instead of 5
        except Exception as e:
            logging.error(f"Cleanup task error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
