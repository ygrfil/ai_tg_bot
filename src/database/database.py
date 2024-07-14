import sqlite3
from contextlib import closing
import json
from datetime import datetime

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

def get_allowed_users():
    return db_operation(lambda c: c.execute('SELECT username FROM allowed_users').fetchall())

def add_allowed_user(username):
    db_operation(lambda c: c.execute('INSERT OR REPLACE INTO allowed_users (username) VALUES (?)', (username,)))
    return True

def is_user_allowed(user_id):
    username = get_username_by_id(user_id)
    result = db_operation(lambda c: c.execute('SELECT 1 FROM allowed_users WHERE username = ?', (username,)).fetchone())
    return bool(result)

def get_username_by_id(user_id):
    # This function should be implemented to get the username from the Telegram API
    # For now, we'll return None as a placeholder
    return None

def remove_allowed_user(username):
    result = db_operation(lambda c: c.execute('DELETE FROM allowed_users WHERE username = ?', (username,)))
    return result.rowcount > 0

def is_user_allowed(user_id):
    username = get_username_by_id(user_id)
    result = db_operation(lambda c: c.execute('SELECT 1 FROM allowed_users WHERE username = ?', (username,)).fetchone())
    return bool(result)

def get_username_by_id(user_id):
    # This function should be implemented to get the username from the Telegram API
    # For now, we'll return None as a placeholder
    return None

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
        CREATE TABLE IF NOT EXISTS allowed_users (
            username TEXT PRIMARY KEY
        )
    '''))
