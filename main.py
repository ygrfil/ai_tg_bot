import os, time, sqlite3, base64, json, tempfile
from contextlib import closing
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Voice
import speech_recognition as sr
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

AVAILABLE_MODELS = ["openai", "anthropic", "perplexity", "groq"]

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
    db_operation(lambda c: c.execute('''
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id INTEGER,
            model TEXT,
            messages_count INTEGER,
            tokens_count INTEGER
        )
    '''))
    db_operation(lambda c: c.execute('''
        CREATE TABLE IF NOT EXISTS conversation_contexts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            context_name TEXT,
            context_data TEXT,
            UNIQUE(user_id, context_name)
        )
    '''))

def get_user_preferences(user_id):
    result = db_operation(lambda c: c.execute('SELECT selected_model FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone())
    return {'selected_model': result[0] if result else 'anthropic'}

def save_user_preferences(user_id, selected_model):
    db_operation(lambda c: c.execute('INSERT OR REPLACE INTO user_preferences (user_id, selected_model) VALUES (?, ?)', (user_id, selected_model)))

def ensure_user_preferences(user_id):
    db_operation(lambda c: c.execute('INSERT OR IGNORE INTO user_preferences (user_id, selected_model) VALUES (?, ?)', (user_id, 'anthropic')))

def log_usage(user_id, model, messages_count, tokens_count):
    today = datetime.now().strftime('%Y-%m-%d')
    db_operation(lambda c: c.execute('''
        INSERT INTO usage_stats (date, user_id, model, messages_count, tokens_count)
        VALUES (?, ?, ?, ?, ?)
    ''', (today, user_id, model, messages_count, tokens_count)))

def get_monthly_usage():
    return db_operation(lambda c: c.execute('''
        SELECT user_id, 
               SUM(messages_count) as total_messages, 
               SUM(tokens_count) as total_tokens
        FROM usage_stats
        WHERE date >= date('now', 'start of month')
        GROUP BY user_id
        ORDER BY total_messages DESC
    ''').fetchall())

def get_user_monthly_usage(user_id):
    return db_operation(lambda c: c.execute('''
        SELECT SUM(messages_count) as total_messages, 
               SUM(tokens_count) as total_tokens
        FROM usage_stats
        WHERE date >= date('now', 'start of month')
        AND user_id = ?
    ''', (user_id,)).fetchone())

def save_conversation_context(user_id, context_name):
    context = json.dumps(user_conversation_history.get(user_id, []))
    db_operation(lambda c: c.execute('''
        INSERT OR REPLACE INTO conversation_contexts (user_id, context_name, context_data)
        VALUES (?, ?, ?)
    ''', (user_id, context_name, context)))

def load_conversation_context(user_id, context_name):
    result = db_operation(lambda c: c.execute('''
        SELECT context_data FROM conversation_contexts
        WHERE user_id = ? AND context_name = ?
    ''', (user_id, context_name)).fetchone())
    if result:
        user_conversation_history[user_id] = json.loads(result[0])
        return True
    return False

def get_username(user_id):
    try:
        user = bot.get_chat_member(user_id, user_id).user
        return user.username or f"{user.first_name} {user.last_name}".strip()
    except ApiTelegramException:
        return f"Unknown User ({user_id})"

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

@bot.message_handler(commands=['model', 'sm', 'broadcast', 'usage', 'my_usage', 'save_context', 'load_context', 'list_prompts'])
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
        handle_broadcast(message)
    elif command == 'usage':
        handle_usage(message)
    elif command == 'my_usage':
        handle_my_usage(message)
    elif command == 'save_context':
        handle_save_context(message)
    elif command == 'load_context':
        handle_load_context(message)
    elif command == 'list_prompts':
        handle_list_prompts(message)

def handle_broadcast(message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    if len(message.text.split(maxsplit=1)) < 2:
        bot.reply_to(message, "Please provide a message to broadcast after the /broadcast command.")
        return
    broadcast_message = message.text.split(maxsplit=1)[1]
    success_count = sum(1 for user_id in ENV["ALLOWED_USER_IDS"] if send_broadcast(int(user_id), broadcast_message))
    bot.reply_to(message, f"Broadcast sent successfully to {success_count} out of {len(ENV['ALLOWED_USER_IDS'])} allowed users.")

def handle_usage(message: Message) -> None:
    if str(message.from_user.id) not in ENV["ADMIN_USER_IDS"]:
        bot.reply_to(message, "Sorry, you are not authorized to use this command.")
        return
    usage_stats = get_monthly_usage()
    usage_report = "Monthly Usage Report (from the start of the current month):\n\n"
    for user_id, messages, tokens in usage_stats:
        username = get_username(user_id)
        usage_report += f"User: {username}\n"
        usage_report += f"Total Messages: {messages}\n"
        usage_report += f"Estimated Tokens: {tokens}\n\n"
    bot.reply_to(message, usage_report)

def handle_my_usage(message: Message) -> None:
    user_id = message.from_user.id
    usage_stats = get_user_monthly_usage(user_id)
    if usage_stats:
        messages, tokens = usage_stats
        usage_report = f"Your Monthly Usage (from the start of the current month):\n\n"
        usage_report += f"Total Messages: {messages}\n"
        usage_report += f"Estimated Tokens: {tokens}\n"
    else:
        usage_report = "You haven't used the bot this month."
    bot.reply_to(message, usage_report)

def handle_save_context(message: Message) -> None:
    user_id = message.from_user.id
    context_name = message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) > 1 else "default"
    save_conversation_context(user_id, context_name)
    bot.reply_to(message, f"Conversation context saved as '{context_name}'.")

def handle_load_context(message: Message) -> None:
    user_id = message.from_user.id
    context_name = message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) > 1 else "default"
    if load_conversation_context(user_id, context_name):
        bot.reply_to(message, f"Conversation context '{context_name}' loaded successfully.")
    else:
        bot.reply_to(message, f"No saved context found with name '{context_name}'.")

def handle_list_prompts(message: Message) -> None:
    prompts = get_system_prompts()
    prompt_list = "Available system prompts:\n\n" + "\n".join(prompts.keys())
    bot.reply_to(message, prompt_list)

# Remove the handle_set_default function entirely

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

@bot.message_handler(content_types=['text', 'photo', 'voice'])
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
        
        # Handle voice messages differently
        if message.content_type == 'voice':
            response = llm.invoke(messages)
        else:
            response = llm.invoke(messages)
        
        # Always add the AI response to the conversation history, regardless of the model
        user_conversation_history[user_id].append(AIMessage(content=stream_handler.response))
        
        # Log usage
        messages_count = 1  # We count this as one interaction
        tokens_count = len(stream_handler.response.split())  # Rough estimate of tokens
        log_usage(user_id, selected_model, messages_count, tokens_count)
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
    elif message.content_type == 'voice':
        return process_voice_message(message)
    return HumanMessage(content=message.text)

def get_llm(selected_model: str, stream_handler: StreamHandler):
    llm_config = {
        "openai": (ChatOpenAI, {"api_key": ENV["OPENAI_API_KEY"], "model": "gpt-4o"}),
        "anthropic": (ChatAnthropic, {"api_key": ENV["ANTHROPIC_API_KEY"], "model": "claude-3-5-sonnet-20240620"}),
        "perplexity": (ChatPerplexity, {"model": "llama-3-sonar-large-32k-online"}),
        "groq": (ChatGroq, {"model_name": "llama3-70b-8192"}),
    }
    
    if selected_model not in llm_config:
        raise ValueError(f"Unknown model: {selected_model}")
    
    LLMClass, kwargs = llm_config[selected_model]
    return LLMClass(streaming=True, callbacks=[stream_handler], **kwargs)

def get_conversation_messages(user_id: int, selected_model: str):
    if selected_model == "perplexity":
        # For Perplexity model, return only the system message and the last human message
        messages = [msg for msg in user_conversation_history[user_id] if isinstance(msg, SystemMessage)]
        human_messages = [msg for msg in user_conversation_history[user_id] if isinstance(msg, HumanMessage)]
        if human_messages:
            messages.append(human_messages[-1])
        return messages
    
    messages = [msg if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)) else SystemMessage(content=msg['content']) for msg in user_conversation_history[user_id]]
    
    # Ensure the first non-system message is a HumanMessage for Anthropic
    if selected_model == "anthropic":
        first_non_system = next((i for i, msg in enumerate(messages) if not isinstance(msg, SystemMessage)), None)
        if first_non_system is not None and not isinstance(messages[first_non_system], HumanMessage):
            messages[first_non_system] = HumanMessage(content=messages[first_non_system].content)
    
    return messages

import base64

def process_voice_message(message: Message) -> HumanMessage:
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Encode the audio file to base64
    audio_base64 = base64.b64encode(downloaded_file).decode('utf-8')
    
    return HumanMessage(content=[
        {"type": "text", "text": "Please transcribe and respond to this voice message:"},
        {"type": "audio", "audio": f"data:audio/ogg;base64,{audio_base64}"}
    ])

def main() -> None:
    init_db()
    bot.polling()

if __name__ == "__main__":
    main()
