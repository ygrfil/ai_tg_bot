from bot import create_bot, import_allowed_users, setup_bot_handlers
from src.database.database import init_db
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting the bot...")
        bot = create_bot()
        logger.info("Bot created successfully")
        
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized")
        
        logger.info("Importing allowed users...")
        import_allowed_users()
        logger.info("Allowed users imported")
        
        logger.info("Setting up bot handlers...")
        setup_bot_handlers(bot)
        logger.info("Bot handlers set up")
        
        logger.info("Starting bot polling...")
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        logger.error(f"Error in main function: {e}", exc_info=True)
    finally:
        logger.info("Bot polling stopped")

if __name__ == "__main__":
    main()
