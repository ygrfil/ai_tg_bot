import os, time, sqlite3, base64
from contextlib import closing
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatPerplexity
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.callbacks.base import BaseCallbackHandler

load_dotenv()

# Environment variables
ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "ALLOWED_USER_IDS": set(os.getenv("ALLOWED_USER_IDS", "").split(",")),
    "ADMIN_USER_IDS": set(os.getenv("ADMIN_USER_IDS", "").split(",")),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "PPLX_API_KEY": os.getenv("PPLX_API_KEY"),
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
}

bot = TeleBot(ENV["TELEGRAM_BOT_TOKEN"])
user_conversation_history = {}
last_interaction_time = {}

def db_operation(operation, *args):
    with closing(sqlite3.connect('user_preferences.db')) as conn, closing(conn.cursor()) as cursor:
        result = operation(cursor, *args)
        conn.commit()
    return result

def init_db():
    db_operation(lambda c: c.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            selected_model TEXT DEFAULT 'anthropic'
        )
    '''))

def get_user_preferences(user_id):
    result = db_operation(lambda c: c.execute('SELECT selected_model FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone())
    return {'selected_model': result[0] if result else 'anthropic'}

def save_user_preferences(user_id, selected_model):
    db_operation(lambda c: c.execute('INSERT OR REPLACE INTO user_preferences (user_id, selected_model) VALUES (?, ?)', (user_id, selected_model)))

def ensure_user_preferences(user_id):
    db_operation(lambda c: c.execute('INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)', (user_id,)))

def is_authorized(message: Message) -> bool:
    return str(message.from_user.id) in ENV["ALLOWED_USER_IDS"] or str(message.from_user.id) in ENV["ADMIN_USER_IDS"]

def reset_conversation_if_needed(user_id: int) -> None:
    if datetime.now() - last_interaction_time.get(user_id, datetime.min) > timedelta(hours=2):
        user_conversation_history[user_id] = []
    last_interaction_time[user_id] = datetime.now()

def limit_conversation_history(user_id: int) -> None:
    user_conversation_history[user_id] = user_conversation_history[user_id][-10:]

def handle_api_error(e: ApiTelegramException, message: Message) -> None:
    if e.error_code == 429:
        time.sleep(int(e.result_json['parameters']['retry_after']))
        handle_message(message)
    else:
        print(f"Error: {e}")

def create_keyboard(buttons) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data)] for text, data in buttons])

def get_system_prompts():
    return {filename[:-4]: open(os.path.join('system_prompts', filename), 'r').read().strip()
            for filename in os.listdir('system_prompts') if filename.endswith('.txt')}

@bot.message_handler(commands=['model', 'sm', 'broadcast'])
def handle_commands(message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    command = message.text.split()[0][1:]
    if command == 'model':
        ensure_user_preferences(message.from_user.id)
        bot.send_message(message.chat.id, "Select a model:", reply_markup=create_keyboard([
            ("OpenAI", "model_openai"),
            ("Anthropic", "model_anthropic"),
            ("Perplexity", "model_perplexity"),
            ("Groq", "model_groq")
        ]))
    elif command == 'sm':
        ensure_user_preferences(message.from_user.id)
        bot.send_message(message.chat.id, "Select a system message:", reply_markup=create_keyboard([(name, f"sm_{name}") for name in get_system_prompts()]))
    elif command == 'broadcast':
        if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
            bot.reply_to(message, "Sorry, you are not authorized to use this command.")
            return
        if len(message.text.split(maxsplit=1)) < 2:
            bot.reply_to(message, "Please provide a message to broadcast after the /broadcast command.")
            return
        broadcast_message = message.text.split(maxsplit=1)[1]
        success_count = sum(1 for user_id in ENV["ALLOWED_USER_IDS"] if send_broadcast(int(user_id), broadcast_message))
        bot.reply_to(message, f"Broadcast sent successfully to {success_count} out of {len(ENV['ALLOWED_USER_IDS'])} allowed users.")

def send_broadcast(user_id: int, message: str) -> bool:
    try:
        bot.send_message(user_id, message)
        return True
    except ApiTelegramException as e:
        print(f"Failed to send broadcast to user {user_id}: {e}")
        return False

@bot.callback_query_handler(func=lambda call: call.data.startswith(('model_', 'sm_')))
def callback_query(call):
    user_id = call.from_user.id
    ensure_user_preferences(user_id)
    if call.data.startswith('model_'):
        model_name = call.data.split('_')[1]
        save_user_preferences(user_id, model_name)
        bot.answer_callback_query(call.id, f"Switched to {model_name} model.")
    else:
        prompt_name = call.data.split('_')[1]
        system_message = get_system_prompts().get(prompt_name, "You are a helpful assistant.")
        user_conversation_history[user_id] = [{"role": "system", "content": system_message}]
        bot.answer_callback_query(call.id, f"Switched to {prompt_name} system message.")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

@bot.message_handler(commands=['start'])
def start_command(message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    bot.reply_to(message, "Welcome! Here are the available commands:\n"
                          "/start: Introduces the bot and explains the available AI models.\n"
                          "/model: Select the AI model (OpenAI, Anthropic, or Groq).\n"
                          "/sm: Select a system message to set the AI behavior and context.\n"
                          "/reset: Reset the conversation history.\n"
                          "/summarize: Summarize the current conversation.\n"
                          "/broadcast: (Admin only) Send a message to all users.\n"
                          "/create_prompt: Create a new system prompt.\n"
                          "Created by Yegor")

@bot.message_handler(commands=['reset'])
def reset_command(message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    user_conversation_history[message.from_user.id] = []
    bot.reply_to(message, "Conversation has been reset.")

@bot.message_handler(commands=['summarize'])
def summarize_command(message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    ensure_user_preferences(message.from_user.id)
    user_id = message.from_user.id
    if user_id not in user_conversation_history or not user_conversation_history[user_id]:
        bot.reply_to(message, "There's no conversation to summarize.")
        return
    placeholder_message = bot.send_message(message.chat.id, "Generating summary...")
    summary = summarize_conversation(user_conversation_history[user_id])
    bot.edit_message_text(summary, chat_id=message.chat.id, message_id=placeholder_message.message_id)

def summarize_conversation(conversation_history):
    summary_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant that summarizes conversations."),
        ("human", "Summarize the following conversation concisely:\n{conversation}")
    ])
    llm = ChatAnthropic(api_key=ENV["ANTHROPIC_API_KEY"], model="claude-3-5-sonnet-20240620")
    chain = summary_prompt | llm | StrOutputParser()
    conversation_text = "\n".join([f"{type(msg).__name__}: {msg.content}" for msg in conversation_history])
    return chain.invoke({"conversation": conversation_text})

@bot.message_handler(commands=['create_prompt'])
def create_prompt_command(message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return
    bot.reply_to(message, "Please send the name for your new system prompt.")
    bot.register_next_step_handler(message, process_prompt_name)

def process_prompt_name(message: Message) -> None:
    prompt_name = message.text.strip()
    if not prompt_name:
        bot.reply_to(message, "Invalid prompt name. Please try again with a valid name.")
        return
    bot.reply_to(message, f"Great! Now send the content for the '{prompt_name}' system prompt.")
    bot.register_next_step_handler(message, lambda m: process_prompt_content(m, prompt_name))

def process_prompt_content(message: Message, prompt_name: str) -> None:
    prompt_content = message.text.strip()
    if not prompt_content:
        bot.reply_to(message, "Invalid prompt content. Please try again with valid content.")
        return
    with open(f"system_prompts/{prompt_name}.txt", 'w') as file:
        file.write(prompt_content)
    bot.reply_to(message, f"System prompt '{prompt_name}' has been created and saved successfully!")

class StreamHandler(BaseCallbackHandler):
    def __init__(self, bot, chat_id, message_id):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.response = ""
        self.last_update_time = time.time()
        self.update_interval = 0.3
        self.max_message_length = 4096

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.response += token
        if time.time() - self.last_update_time >= self.update_interval:
            self.update_message()

    def update_message(self):
        try:
            update_text = self.response[-self.max_message_length:] if len(self.response) > self.max_message_length else self.response
            if update_text.strip():
                self.bot.edit_message_text(update_text, chat_id=self.chat_id, message_id=self.message_id)
                self.last_update_time = time.time()
        except ApiTelegramException as e:
            if e.error_code != 429:
                print(f"Error updating message: {e}")

    def on_llm_end(self, response: str, **kwargs) -> None:
        self.update_message()

@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message: Message) -> None:
    if not is_authorized(message):
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    user_id = message.from_user.id
    ensure_user_preferences(user_id)
    user_prefs = get_user_preferences(user_id)
    selected_model = user_prefs['selected_model']

    reset_conversation_if_needed(user_id)

    user_message = process_message_content(message)
    user_conversation_history.setdefault(user_id, []).append(user_message)
    limit_conversation_history(user_id)

    placeholder_message = bot.send_message(message.chat.id, "Generating...")

    try:
        stream_handler = StreamHandler(bot, message.chat.id, placeholder_message.message_id)
        llm = get_llm(selected_model, stream_handler)
        messages = get_conversation_messages(user_id, selected_model)
        response = llm.invoke(messages)
        user_conversation_history[user_id].append(AIMessage(content=stream_handler.response))
    except ApiTelegramException as e:
        handle_api_error(e, message)

def process_message_content(message: Message) -> HumanMessage:
    if message.content_type == 'photo':
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image_url = f"data:image/jpeg;base64,{base64.b64encode(downloaded_file).decode('utf-8')}"
        return HumanMessage(content=[
            {"type": "text", "text": message.caption or "Analyze this image."},
            {"type": "image_url", "image_url": {"url": image_url}}
        ])
    return HumanMessage(content=message.text)

def get_llm(selected_model: str, stream_handler: StreamHandler):
    llm_config = {
        "openai": (ChatOpenAI, {"api_key": ENV["OPENAI_API_KEY"], "model": "gpt-4o"}),
        "anthropic": (ChatAnthropic, {"api_key": ENV["ANTHROPIC_API_KEY"], "model": "claude-3-5-sonnet-20240620"}),
        "perplexity": (ChatPerplexity, {"model": "lama-3-sonar-large-32k-online"}),
        "groq": (ChatGroq, {"model_name": "llama3-70b-8192"}),
    }
    
    if selected_model not in llm_config:
        raise ValueError(f"Unknown model: {selected_model}")
    
    LLMClass, kwargs = llm_config[selected_model]
    return LLMClass(streaming=True, callbacks=[stream_handler], **kwargs)

def get_conversation_messages(user_id: int, selected_model: str):
    if selected_model == "perplexity":
        return [msg for msg in user_conversation_history[user_id] if isinstance(msg, (HumanMessage, AIMessage))]
    return [msg if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)) else SystemMessage(content=msg['content']) for msg in user_conversation_history[user_id]]

def main() -> None:
    init_db()
    bot.polling()

if __name__ == "__main__":
    main()