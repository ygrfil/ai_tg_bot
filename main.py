from bot import create_bot, import_allowed_users, setup_bot_handlers
from src.database.database import init_db
import logging
import time

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        max_retries = 5
        retry_delay = 5  # initial delay in seconds

        for attempt in range(max_retries):
            try:
                bot.polling(none_stop=True, timeout=60)
                break  # Exit loop if polling starts successfully
            except Exception as e:
                logger.error(f"Polling error: {e}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        else:
            logger.error("Max retries reached. Exiting.")
    except Exception as e:
        logger.error(f"Error in main function: {e}", exc_info=True)
    finally:
        logger.info("Bot polling stopped")

if __name__ == "__main__":
    main()
