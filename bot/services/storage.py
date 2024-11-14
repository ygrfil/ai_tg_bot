from typing import Dict, Any, List, Optional
from datetime import datetime
import aiosqlite
import os
import logging
import asyncio
from contextlib import asynccontextmanager
import json

class Storage:
    def __init__(self, db_path: str = "data/chat.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._initialized = False
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def _db_connect(self):
        """Context manager for database connections with retry logic"""
        for attempt in range(3):  # Reduced retries to 3
            try:
                async with aiosqlite.connect(self.db_path, timeout=10.0) as db:  # Reduced timeout
                    await db.execute("PRAGMA journal_mode=WAL")  # Enable Write-Ahead Logging
                    await db.execute("PRAGMA synchronous=NORMAL")  # Faster synchronization
                    await db.execute("PRAGMA cache_size=-64000")  # 64MB cache
                    yield db
                break
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    await asyncio.sleep(0.1 * (attempt + 1))  # Shorter backoff
                else:
                    raise

    async def ensure_initialized(self):
        """Initialize database tables if they don't exist"""
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    # Create users table with all required columns
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            current_provider TEXT DEFAULT 'claude',
                            current_model TEXT DEFAULT 'claude-3-sonnet',
                            settings TEXT,
                            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    # Create chat_history table
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS chat_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            content TEXT,
                            image_data BLOB,
                            is_bot BOOLEAN,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id)
                        )
                    """)

                    # Check and add missing columns for users table
                    async with db.execute("PRAGMA table_info(users)") as cursor:
                        columns = await cursor.fetchall()
                        column_names = [col[1] for col in columns]
                        
                        if 'username' not in column_names:
                            await db.execute("ALTER TABLE users ADD COLUMN username TEXT")
                        if 'current_provider' not in column_names:
                            await db.execute("ALTER TABLE users ADD COLUMN current_provider TEXT DEFAULT 'claude'")
                        if 'current_model' not in column_names:
                            await db.execute("ALTER TABLE users ADD COLUMN current_model TEXT DEFAULT 'claude-3-sonnet'")

                    # Check and add missing columns for chat_history table
                    async with db.execute("PRAGMA table_info(chat_history)") as cursor:
                        columns = await cursor.fetchall()
                        column_names = [col[1] for col in columns]
                        
                        if 'image_data' not in column_names:
                            await db.execute("ALTER TABLE chat_history ADD COLUMN image_data BLOB")

                    await db.commit()

            except Exception as e:
                logging.error(f"Database initialization error: {e}")
                raise

    async def get_user_settings(self, user_id: int) -> Optional[dict]:
        """Get user settings from database"""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT settings, current_provider, current_model
                    FROM users 
                    WHERE user_id = ?
                """, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        settings = json.loads(row[0]) if row[0] else {}
                        # Merge column values with JSON settings
                        settings.update({
                            'current_provider': row[1] or 'claude',
                            'current_model': row[2] or 'claude-3-sonnet'
                        })
                        return settings
                    return None
        except Exception as e:
            logging.error(f"Error getting user settings: {e}")
            return None

    async def save_user_settings(self, user_id: int, settings: dict):
        """Save user settings to database"""
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    # Update both settings JSON and individual columns
                    await db.execute("""
                        UPDATE users 
                        SET settings = ?,
                            current_provider = ?,
                            current_model = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (
                        json.dumps(settings),
                        settings.get('current_provider'),
                        settings.get('current_model'),
                        user_id
                    ))
                    await db.commit()
            except Exception as e:
                logging.error(f"Error saving user settings: {e}")
                raise

    async def add_message(self, user_id: int, content: str, is_bot: bool, image_data: Optional[bytes] = None):
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    # If this is a new message with an image, remove previous image messages
                    if image_data:
                        await db.execute("""
                            UPDATE chat_history 
                            SET image_data = NULL 
                            WHERE user_id = ? AND image_data IS NOT NULL
                        """, (user_id,))
                    
                    await db.execute(
                        """INSERT INTO chat_history (user_id, content, is_bot, image_data) 
                           VALUES (?, ?, ?, ?)""",
                        (user_id, content, is_bot, image_data)
                    )
                    await db.commit()
            except Exception as e:
                logging.error(f"Error adding message: {e}")
                raise

    async def get_chat_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get chat history for a user"""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT content, image_data, is_bot, timestamp 
                    FROM chat_history 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    history = []
                    for row in rows:
                        message = {
                            "content": row[0],
                            "is_bot": row[2],
                            "timestamp": row[3]
                        }
                        if row[1]:  # image_data
                            message["image"] = row[1]
                        history.append(message)
                    return list(reversed(history))  # Return in chronological order
        except Exception as e:
            logging.error(f"Error getting chat history: {e}")
            return []

    async def clear_user_history(self, user_id: int):
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    await db.execute(
                        "DELETE FROM chat_history WHERE user_id = ?",
                        (user_id,)
                    )
                    await db.commit()
            except Exception as e:
                logging.error(f"Error clearing user history: {e}")
                raise

    async def cleanup_old_history(self):
        """Clear chat history older than 2 hours"""
        await self.ensure_initialized()
        async with self._lock:
            async with self._db_connect() as db:
                # First, get the image data that needs to be cleaned up
                await db.execute("""
                    DELETE FROM chat_history 
                    WHERE datetime(timestamp) < datetime('now', '-2 hours')
                """)
                await db.commit()

    async def update_last_activity(self, user_id: int):
        """Update user's last activity timestamp"""
        await self.ensure_initialized()
        async with self._lock:
            async with self._db_connect() as db:
                await db.execute(
                    "UPDATE users SET last_activity = datetime('now') WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()

    async def cleanup_inactive_users(self):
        """Clear chat history for users inactive for 2 hours"""
        await self.ensure_initialized()
        async with self._lock:
            async with self._db_connect() as db:
                # Get users who have been inactive for 2 hours
                async with db.execute("""
                    SELECT user_id FROM users 
                    WHERE datetime(last_activity) < datetime('now', '-2 hours')
                """) as cursor:
                    inactive_users = await cursor.fetchall()
                
                # Clear history for each inactive user
                for (user_id,) in inactive_users:
                    await db.execute(
                        "DELETE FROM chat_history WHERE user_id = ?",
                        (user_id,)
                    )
                    logging.info(f"Cleared chat history for inactive user {user_id}")
                
                await db.commit()

    async def ensure_user_exists(self, user_id: int, username: str = None):
        """Ensure user exists in database and update username if provided"""
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    # First try to update existing user's username
                    await db.execute("""
                        INSERT INTO users (user_id, username) 
                        VALUES (?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET 
                            username = CASE 
                                WHEN ? IS NOT NULL THEN ?
                                ELSE users.username
                            END
                    """, (user_id, username, username, username))
                    await db.commit()
            except Exception as e:
                logging.error(f"Error ensuring user exists: {e}")
                raise

    async def log_usage(self, user_id: int, provider: str, tokens: int = 0, has_image: bool = False):
        """Log usage statistics for a user and provider"""
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    await db.execute("""
                        INSERT INTO usage_stats 
                        (user_id, provider, message_count, token_count, image_count) 
                        VALUES (?, ?, 1, ?, ?)
                    """, (user_id, provider, tokens, 1 if has_image else 0))
                    await db.commit()
            except Exception as e:
                logging.error(f"Error logging usage: {e}")

    async def get_usage_stats(self, period: str = 'month') -> Dict[str, Any]:
        """Get usage statistics for all users"""
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    # Get total users
                    async with db.execute("SELECT COUNT(DISTINCT user_id) FROM users") as cursor:
                        total_users = (await cursor.fetchone())[0]

                    # Get active users in the last 24 hours
                    async with db.execute("""
                        SELECT COUNT(DISTINCT user_id) FROM users 
                        WHERE datetime(last_activity) > datetime('now', '-1 day')
                    """) as cursor:
                        active_users_24h = (await cursor.fetchone())[0]

                    # Get monthly usage per provider
                    async with db.execute("""
                        SELECT 
                            provider,
                            COUNT(DISTINCT user_id) as unique_users,
                            SUM(message_count) as total_messages,
                            SUM(token_count) as total_tokens,
                            SUM(image_count) as total_images
                        FROM usage_stats 
                        WHERE datetime(timestamp) > datetime('now', '-30 day')
                        GROUP BY provider
                    """) as cursor:
                        provider_stats = await cursor.fetchall()

                    # Get top users
                    async with db.execute("""
                        SELECT 
                            u.user_id,
                            SUM(us.message_count) as total_messages,
                            COUNT(DISTINCT us.provider) as providers_used
                        FROM users u
                        JOIN usage_stats us ON u.user_id = us.user_id
                        WHERE datetime(us.timestamp) > datetime('now', '-30 day')
                        GROUP BY u.user_id
                        ORDER BY total_messages DESC
                        LIMIT 5
                    """) as cursor:
                        top_users = await cursor.fetchall()

                    return {
                        "total_users": total_users,
                        "active_users_24h": active_users_24h,
                        "provider_stats": provider_stats,
                        "top_users": top_users
                    }
            except Exception as e:
                logging.error(f"Error getting usage stats: {e}")
                return {}
