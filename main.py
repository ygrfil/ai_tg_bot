import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.client.default import DefaultBotProperties

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
    
    # Start polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
