from telebot import TeleBot
from config import ENV
from database import init_db
from handlers import (handle_commands, callback_query_handler, start_command,
                      reset_command, summarize_command, create_prompt_command, handle_message)

bot = TeleBot(ENV["TELEGRAM_BOT_TOKEN"])

@bot.message_handler(commands=['model', 'sm', 'broadcast', 'usage'])
def command_handler(message):
    handle_commands(bot, message)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('model_', 'sm_')))
def callback_query(call):
    callback_query_handler(bot, call)

@bot.message_handler(commands=['start'])
def start(message):
    start_command(bot, message)

@bot.message_handler(commands=['reset'])
def reset(message):
    reset_command(bot, message)

@bot.message_handler(commands=['summarize'])
def summarize(message):
    summarize_command(bot, message)

@bot.message_handler(commands=['create_prompt'])
def create_prompt(message):
    create_prompt_command(bot, message)

@bot.message_handler(content_types=['text', 'photo'])
def message_handler(message):
    handle_message(bot, message)

def main():
    init_db()
    bot.polling()

if __name__ == "__main__":
    main()
