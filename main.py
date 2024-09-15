from bot import create_bot, import_allowed_users, setup_bot_handlers
from src.database.database import init_db
import logging
import time
from config import ENV

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_polling(bot, max_retries=5, initial_retry_delay=5):
    logger.info("Starting bot polling...")
    retry_delay = initial_retry_delay

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

def main():
    logger.info("Starting the bot...")
    logger.info(f"GOOGLE_API_KEY is {'set' if ENV.get('GOOGLE_API_KEY') else 'not set'}")
    try:
        bot = create_bot()
        logger.info("Bot created successfully")
        
        init_db()
        logger.info("Database initialized")
        
        import_allowed_users()
        logger.info("Allowed users imported")
        
        setup_bot_handlers(bot)
        logger.info("Bot handlers set up")
        
        start_polling(bot)
    except Exception as e:
        logger.error(f"Error in main function: {e}", exc_info=True)
    finally:
        logger.info("Bot polling stopped")

if __name__ == "__main__":
    main()
