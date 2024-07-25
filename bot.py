from telebot import TeleBot
from config import ENV
from src.database.database import init_db, add_allowed_user
from src.handlers.handlers import (handle_commands, callback_query_handler, start_command,
                      startadmin_command, reset_command, summarize_command, create_prompt_command, handle_message)

try:
    bot = TeleBot(ENV["TELEGRAM_BOT_TOKEN"])
except Exception as e:
    print(f"Error initializing bot: {e}")
    raise

@bot.message_handler(commands=['model', 'sm', 'broadcast', 'usage', 'list_users', 'add_user', 'remove_user', 'remove_prompt', 'status'])
def command_handler(message):
    handle_commands(bot, message)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('model_', 'sm_')))
def callback_query(call):
    callback_query_handler(bot, call)

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
    handle_message(bot, message)

def import_allowed_users():
    allowed_users = ENV.get("ALLOWED_USER_IDS", [])
    for user_id in allowed_users:
        if isinstance(user_id, str) and user_id.strip():
            add_allowed_user(int(user_id.strip()))
        elif isinstance(user_id, int):
            add_allowed_user(user_id)

def main():
    try:
        init_db()
        import_allowed_users()
        bot.polling()
    except Exception as e:
        print(f"Error in main function: {e}")
        raise

if __name__ == "__main__":
    main()
