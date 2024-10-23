from telebot import TeleBot
from telebot.apihelper import ApiException
from config import ENV
from src.database.database import init_db, add_allowed_user
from src.handlers.handlers import (handle_commands, callback_query_handler, start_command,
                      startadmin_command, reset_command, handle_message)
import logging
import time
import requests

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY = 5

def create_bot() -> TeleBot:
    """Create and return a TeleBot instance."""
    if not (token := ENV.get("TELEGRAM_BOT_TOKEN")):
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    return TeleBot(token)

def setup_bot_handlers(bot):
    logger.info("Setting up bot handlers...")

    @bot.message_handler(commands=['model', 'sm', 'broadcast', 'usage', 'list_users', 'add_user', 'remove_user', 'remove_prompt', 'status', 'reload'])
    def command_handler(message):
        try:
            logger.info(f"Received command: {message.text}")
            handle_commands(bot, message)
        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            bot.reply_to(message, "An error occurred while processing your command. Please try again later.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('model_', 'sm_')))
    def callback_query(call):
        try:
            logger.info(f"Received callback query: {call.data}")
            callback_query_handler(bot, call)
        except Exception as e:
            logger.error(f"Error handling callback query: {e}", exc_info=True)
            bot.answer_callback_query(call.id, "An error occurred. Please try again.")

    @bot.message_handler(commands=['start'])
    def start(message):
        logger.info("Received /start command")
        start_command(bot, message)

    @bot.message_handler(commands=['startadmin'])
    def startadmin(message):
        logger.info("Received /startadmin command")
        startadmin_command(bot, message)

    @bot.message_handler(commands=['reset'])
    def reset(message):
        logger.info("Received /reset command")
        reset_command(bot, message)


    @bot.message_handler(content_types=['text', 'photo'])
    def message_handler(message):
        try:
            if message.content_type == 'text':
                logger.info(f"Received text message: {message.text[:50]}...")
            elif message.content_type == 'photo':
                logger.info("Received photo message")
            handle_message(bot, message)
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            bot.reply_to(message, "An error occurred while processing your message. Please try again later.")

    logger.info("Bot handlers set up successfully")

def import_allowed_users():
    logger.info("Importing allowed users...")
    allowed_users = ENV.get("ALLOWED_USER_IDS", [])
    for user_id in allowed_users:
        if user_id and str(user_id).strip():
            try:
                add_allowed_user(int(str(user_id).strip()))
                logger.info(f"Added allowed user: {user_id}")
            except ValueError as e:
                logger.error(f"Error adding allowed user: {e}", exc_info=True)
    logger.info("Finished importing allowed users")

def main():
    import signal
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping bot gracefully...")
        if 'bot' in locals():
            bot.stop_polling()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.info("Starting bot...")
            bot = create_bot()
            init_db()
            import_allowed_users()
            setup_bot_handlers(bot)
            logger.info("Bot is running...")
            bot.polling(none_stop=True)
        except (ApiException, requests.exceptions.RequestException) as e:
            retries += 1
            logger.error(f"Network error occurred: {e}. Retry {retries}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            retries += 1
            time.sleep(RETRY_DELAY)
    
    logger.error(f"Bot stopped after {MAX_RETRIES} failed attempts")

if __name__ == "__main__":
    main()
