from telebot import TeleBot
from telebot.apihelper import ApiException
from config import ENV
from src.database.database import init_db, add_allowed_user
from src.handlers.handlers import (handle_commands, callback_query_handler, start_command,
                      startadmin_command, reset_command, create_prompt_command, handle_message)
import logging
import time
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY = 5

def create_bot():
    try:
        logger.info("Creating bot instance...")
        bot = TeleBot(ENV["TELEGRAM_BOT_TOKEN"])
        logger.info("Bot instance created successfully")
        return bot
    except KeyError:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        raise
    except Exception as e:
        logger.error(f"Error initializing bot: {e}", exc_info=True)
        raise

def setup_bot_handlers(bot):
    logger.info("Setting up bot handlers...")

    @bot.message_handler(commands=['model', 'sm', 'broadcast', 'usage', 'list_users', 'add_user', 'remove_user', 'remove_prompt', 'status', 'btc'])
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

    @bot.message_handler(commands=['create_prompt'])
    def create_prompt(message):
        logger.info("Received /create_prompt command")
        create_prompt_command(bot, message)

    @bot.message_handler(content_types=['text', 'photo'])
    def message_handler(message):
        try:
            logger.info(f"Received message: {message.text[:50]}...")
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

# The main() function and if __name__ == "__main__": block have been removed.
# The rest of the file remains unchanged.
