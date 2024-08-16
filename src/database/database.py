import sqlite3
from contextlib import closing
import json
from datetime import datetime
from config import ENV
from langchain_core.messages import HumanMessage

def db_operation(operation, *args):
    with closing(sqlite3.connect('user_preferences.db')) as conn:
        with closing(conn.cursor()) as cursor:
            result = operation(cursor, *args)
            conn.commit()
    return result

def init_db():
    db_operation(lambda c: c.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            selected_model TEXT DEFAULT 'anthropic',
            system_prompt TEXT DEFAULT 'standard',
            creativity_level TEXT DEFAULT 'moderate',
            last_interaction TEXT
        )
    '''))
    db_operation(lambda c: c.execute('''
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id INTEGER,
            model TEXT,
            messages_count INTEGER
        )
    '''))

def get_user_preferences(user_id):
    result = db_operation(lambda c: c.execute('SELECT selected_model, system_prompt, creativity_level FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone())
    return {'selected_model': result[0] if result else 'anthropic', 'system_prompt': result[1] if result else 'standard', 'creativity_level': result[2] if result else 'moderate'}

def save_user_preferences(user_id, selected_model=None, system_prompt=None, creativity_level=None):
    current_prefs = get_user_preferences(user_id)
    new_model = selected_model if selected_model is not None else current_prefs['selected_model']
    new_prompt = system_prompt if system_prompt is not None else current_prefs['system_prompt']
    new_creativity = creativity_level if creativity_level is not None else current_prefs['creativity_level']
    db_operation(lambda c: c.execute('INSERT OR REPLACE INTO user_preferences (user_id, selected_model, system_prompt, creativity_level) VALUES (?, ?, ?, ?)', (user_id, new_model, new_prompt, new_creativity)))

def ensure_user_preferences(user_id):
    db_operation(lambda c: c.execute('INSERT OR IGNORE INTO user_preferences (user_id, selected_model, system_prompt, creativity_level) VALUES (?, ?, ?, ?)', (user_id, 'anthropic', 'standard', 'moderate')))

def log_usage(user_id, model, messages_count):
    today = datetime.now().strftime('%Y-%m-%d')
    db_operation(lambda c: c.execute('''
        INSERT INTO usage_stats (date, user_id, model, messages_count)
        VALUES (?, ?, ?, ?)
    ''', (today, user_id, model, messages_count)))

def get_monthly_usage():
    return db_operation(lambda c: c.execute('''
        SELECT user_id, 
               model,
               SUM(messages_count) as total_messages
        FROM usage_stats
        WHERE date >= date('now', 'start of month')
        GROUP BY user_id, model
        ORDER BY user_id, total_messages DESC
    ''').fetchall())

def get_user_monthly_usage(user_id):
    return db_operation(lambda c: c.execute('''
        SELECT SUM(messages_count) as total_messages
        FROM usage_stats
        WHERE date >= date('now', 'start of month')
        AND user_id = ?
    ''', (user_id,)).fetchone())

def get_allowed_users():
    return db_operation(lambda c: c.execute('SELECT user_id, username FROM allowed_users').fetchall())

def add_allowed_user(user_id):
    db_operation(lambda c: c.execute('INSERT OR IGNORE INTO allowed_users (user_id) VALUES (?)', (user_id,)))
    return True

def is_user_allowed(user_id):
    result = db_operation(lambda c: c.execute('SELECT 1 FROM allowed_users WHERE user_id = ?', (user_id,)).fetchone())
    return bool(result) or str(user_id) in ENV["ADMIN_USER_IDS"]

def remove_allowed_user(user_id):
    result = db_operation(lambda c: c.execute('DELETE FROM allowed_users WHERE user_id = ?', (user_id,)))
    return result.rowcount > 0

def update_username(user_id, username):
    db_operation(lambda c: c.execute('UPDATE allowed_users SET username = ? WHERE user_id = ?', (username, user_id)))

def get_last_interaction_time(user_id):
    result = db_operation(lambda c: c.execute('SELECT last_interaction FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone())
    return result[0] if result else None

def update_last_interaction_time(user_id, timestamp):
    db_operation(lambda c: c.execute('UPDATE user_preferences SET last_interaction = ? WHERE user_id = ?', (timestamp, user_id)))

def init_db():
    db_operation(lambda c: c.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            selected_model TEXT DEFAULT 'anthropic',
            system_prompt TEXT DEFAULT 'standard',
            creativity_level TEXT DEFAULT 'moderate',
            last_interaction TEXT
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
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    '''))
    
    # Add indexes for better performance
    db_operation(lambda c: c.execute('CREATE INDEX IF NOT EXISTS idx_usage_stats_user_id ON usage_stats (user_id)'))
    db_operation(lambda c: c.execute('CREATE INDEX IF NOT EXISTS idx_usage_stats_date ON usage_stats (date)'))
    
    # Add indexes for better performance
    db_operation(lambda c: c.execute('CREATE INDEX IF NOT EXISTS idx_usage_stats_user_id ON usage_stats (user_id)'))
    db_operation(lambda c: c.execute('CREATE INDEX IF NOT EXISTS idx_usage_stats_date ON usage_stats (date)'))
    
    # Add system_prompt column if it doesn't exist
    columns = db_operation(lambda c: c.execute('PRAGMA table_info(user_preferences)').fetchall())
    if 'system_prompt' not in [column[1] for column in columns]:
        db_operation(lambda c: c.execute('''
            ALTER TABLE user_preferences
            ADD COLUMN system_prompt TEXT DEFAULT 'standard'
        '''))
    
    # Add creativity_level column if it doesn't exist
    if 'creativity_level' not in [column[1] for column in columns]:
        db_operation(lambda c: c.execute('''
            ALTER TABLE user_preferences
            ADD COLUMN creativity_level TEXT DEFAULT 'moderate'
        '''))

def init_db():
    db_operation(lambda c: c.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            selected_model TEXT DEFAULT 'anthropic',
            system_prompt TEXT DEFAULT 'standard',
            creativity_level TEXT DEFAULT 'moderate',
            last_interaction TEXT
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
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    '''))
    
    # Add last_interaction column if it doesn't exist
    columns = db_operation(lambda c: c.execute('PRAGMA table_info(user_preferences)').fetchall())
    if 'last_interaction' not in [column[1] for column in columns]:
        db_operation(lambda c: c.execute('''
            ALTER TABLE user_preferences
            ADD COLUMN last_interaction TEXT
        '''))
