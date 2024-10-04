from telebot import TeleBot
from src.handlers.handlers import handle_commands, handle_message, callback_query_handler, start_command, startadmin_command, reset_command
from src.database.database import init_db
import logging
from config import ENV

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_bot():
    return TeleBot(ENV["TELEGRAM_BOT_TOKEN"])

def setup_bot_handlers(bot):
    bot.message_handler(commands=['start'])(lambda msg: start_command(bot, msg))
    bot.message_handler(commands=['startadmin'])(lambda msg: startadmin_command(bot, msg))
    bot.message_handler(commands=['reset'])(lambda msg: reset_command(bot, msg))
    bot.message_handler(commands=['model', 'sm', 'broadcast', 'usage', 'list_users', 'add_user', 'remove_user', 'remove_prompt', 'status', 'reload'])(lambda msg: handle_commands(bot, msg))
    bot.message_handler(func=lambda message: True)(lambda msg: handle_message(bot, msg))
    bot.callback_query_handler(func=lambda call: True)(lambda call: callback_query_handler(bot, call))

def main():
    logger.info("Starting the bot...")
    try:
        bot = create_bot()
        logger.info("Bot created successfully")
        
        init_db()
        logger.info("Database initialized")
        
        setup_bot_handlers(bot)
        logger.info("Bot handlers set up")
        
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Error in main function: {e}", exc_info=True)
    finally:
        logger.info("Bot polling stopped")

if __name__ == "__main__":
    main()
