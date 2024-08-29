from telebot import TeleBot
from telebot.apihelper import ApiException
from config import ENV
from src.database.database import init_db, add_allowed_user
from src.handlers.handlers import (handle_commands, callback_query_handler, start_command,
                      startadmin_command, reset_command, create_prompt_command, handle_message)
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    bot = TeleBot(ENV["TELEGRAM_BOT_TOKEN"])
except KeyError:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
    raise
except Exception as e:
    logger.error(f"Error initializing bot: {e}")
    raise

@bot.message_handler(commands=['model', 'sm', 'broadcast', 'usage', 'list_users', 'add_user', 'remove_user', 'remove_prompt', 'status'])
def command_handler(message):
    try:
        handle_commands(bot, message)
    except Exception as e:
        logger.error(f"Error handling command: {e}")
        bot.reply_to(message, "An error occurred while processing your command. Please try again later.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('model_', 'sm_')))
def callback_query(call):
    try:
        callback_query_handler(bot, call)
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        bot.answer_callback_query(call.id, "An error occurred. Please try again.")

@bot.message_handler(commands=['start'])
def start(message):
    start_command(bot, message)

@bot.message_handler(commands=['startadmin'])
def startadmin(message):
    startadmin_command(bot, message)

@bot.message_handler(commands=['reset'])
def reset(message):
    reset_command(bot, message)

@bot.message_handler(commands=['create_prompt'])
def create_prompt(message):
    create_prompt_command(bot, message)

@bot.message_handler(content_types=['text', 'photo'])
def message_handler(message):
    try:
        handle_message(bot, message)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        bot.reply_to(message, "An error occurred while processing your message. Please try again later.")

def import_allowed_users():
    allowed_users = ENV.get("ALLOWED_USER_IDS", [])
    for user_id in allowed_users:
        if user_id and str(user_id).strip():
            try:
                add_allowed_user(int(str(user_id).strip()))
            except ValueError as e:
                logger.error(f"Error adding allowed user: {e}")

def main():
    try:
        init_db()
        import_allowed_users()
        logger.info("Starting bot polling...")
        bot.polling(none_stop=True)
    except ApiException as e:
        logger.error(f"Telegram API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in main function: {e}")
    finally:
        logger.info("Bot polling stopped")

if __name__ == "__main__":
    main()
