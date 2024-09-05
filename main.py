from bot import create_bot, import_allowed_users
from src.database.database import init_db
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        print("Starting the bot...")
        bot = create_bot()
        init_db()
        import_allowed_users()
        logger.info("Starting bot polling...")
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        logger.error(f"Error in main function: {e}")
    finally:
        logger.info("Bot polling stopped")

if __name__ == "__main__":
    main()
