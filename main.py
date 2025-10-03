import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.client.default import DefaultBotProperties

from bot.config import Config
from bot.handlers import admin, user, access_request
from bot.services.storage import Storage
from bot.keyboards import reply as kb
from bot.utils.polling import PollingMiddleware

async def on_startup(bot: Bot, storage: Storage, config: 'Config'):
    """Initialize bot on startup"""
    try:
        # Just log that startup is complete - no database operations needed
        # Database will be initialized when first user interacts
        logging.info("Bot startup complete - database will initialize on first use")
        
        # Pre-warm provider cache for faster first response
        logging.info("Pre-warming AI provider cache...")
        try:
            from bot.services.ai_providers import get_provider
            from bot.services.ai_providers.providers import PROVIDER_MODELS
            
            # Pre-initialize most commonly used providers to eliminate first-request penalty
            common_providers = ["openai", "sonnet", "grok"]
            for provider_name in common_providers:
                if provider_name in PROVIDER_MODELS:
                    try:
                        provider = await get_provider(provider_name, config)
                        logging.info(f"✅ Pre-warmed provider '{provider_name}'")
                    except Exception as e:
                        logging.warning(f"⚠️ Failed to pre-warm provider '{provider_name}': {e}")
                
        except Exception as e:
            logging.error(f"❌ Provider pre-warming failed: {e}")
            
    except Exception as e:
        logging.error(f"Error during startup: {e}")

async def main():
    # Configure logging level from environment variable LOG_LEVEL (default INFO)
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    
    # Reduce verbosity of noisy third-party libraries
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('aiogram.utils.chat_action').setLevel(logging.INFO)
    logging.getLogger('aiogram.event').setLevel(logging.INFO)
    
    logging.getLogger(__name__).info(f"Logging initialized at level: {log_level_name}")
    
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
            parse_mode=ParseMode.HTML,  # HTML allows bold, italic, underline, etc.
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
    dp.include_router(admin.router)   # Admin router first
    dp.include_router(access_request.router)  # Access request router second (handles unauthorized user workflows)
    dp.include_router(user.router)    # User router last (handles authorized users)
    
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
    await on_startup(bot, settings_storage, config)
    
    # Start polling with configured settings
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        polling_timeout=config.polling_settings["timeout"],
        polling_interval=config.polling_settings["poll_interval"]
    )

if __name__ == "__main__":
    asyncio.run(main())
