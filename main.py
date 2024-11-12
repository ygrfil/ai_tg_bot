import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.client.default import DefaultBotProperties
import os

from bot.config import Config
from bot.handlers import admin, user
from bot.services.storage import JsonStorage

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Load config
    config = Config.from_env()
    
    # Initialize storages
    memory_storage = MemoryStorage()  # For FSM
    settings_storage = JsonStorage("data/user_settings.json")
    
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
    
    # Register routers with debug print
    print("[DEBUG] Registering admin router")
    dp.include_router(admin.router)
    print("[DEBUG] Registering user router")
    dp.include_router(user.router)
    
    # Debug file paths
    settings_path = "data/user_settings.json"
    history_path = "data/chat_history.json"
    
    print("\n=== Storage Files ===")
    print(f"Settings path: {os.path.abspath(settings_path)}")
    print(f"History path: {os.path.abspath(history_path)}")
    print(f"Settings exists: {os.path.exists(settings_path)}")
    print(f"History exists: {os.path.exists(history_path)}")
    print("===================\n")
    
    # Start polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
