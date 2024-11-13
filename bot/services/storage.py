from typing import Dict, Any, List
from datetime import datetime
import aiosqlite
import os
import logging
import asyncio
from contextlib import asynccontextmanager

class Storage:
    def __init__(self, db_path: str = "data/chat.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.is_initialized = False
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
        if not self.is_initialized:
            await self._init_db()
            self.is_initialized = True

    async def _init_db(self):
        """Initialize database with all required tables and columns"""
        async with self._lock:
            async with self._db_connect() as db:
                # First create tables if they don't exist
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        current_provider TEXT NOT NULL DEFAULT 'openai',
                        current_model TEXT NOT NULL DEFAULT 'gpt-4',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Check if last_activity column exists
                async with db.execute("PRAGMA table_info(users)") as cursor:
                    columns = await cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    # Add last_activity column if it doesn't exist
                    if 'last_activity' not in column_names:
                        await db.execute("""
                            ALTER TABLE users 
                            ADD COLUMN last_activity DATETIME
                        """)
                        await db.execute("""
                            UPDATE users 
                            SET last_activity = datetime('now')
                            WHERE last_activity IS NULL
                        """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        is_bot BOOLEAN NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                """)
                
                await db.commit()

    async def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    async with db.execute(
                        """SELECT current_provider, current_model 
                           FROM users WHERE user_id = ?""", 
                        (user_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            return {
                                "current_provider": row[0],
                                "current_model": row[1]
                            }
                        
                        # Create default settings if user doesn't exist
                        default_settings = {
                            "current_provider": "openai",
                            "current_model": "gpt-4"
                        }
                        await self.save_user_settings(user_id, default_settings)
                        return default_settings
            except Exception as e:
                logging.error(f"Error getting user settings: {e}")
                return {"current_provider": "openai", "current_model": "gpt-4"}

    async def save_user_settings(self, user_id: int, settings: Dict[str, Any]):
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    await db.execute(
                        """INSERT INTO users (user_id, current_provider, current_model, last_activity) 
                           VALUES (?, ?, ?, datetime('now')) 
                           ON CONFLICT(user_id) DO UPDATE 
                           SET current_provider = ?, 
                               current_model = ?, 
                               last_activity = datetime('now'),
                               updated_at = datetime('now')""",
                        (user_id, settings["current_provider"], settings["current_model"],
                         settings["current_provider"], settings["current_model"])
                    )
                    await db.commit()
            except Exception as e:
                logging.error(f"Error saving user settings: {e}")
                raise

    async def add_message(self, user_id: int, content: str, is_bot: bool):
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    await db.execute(
                        """INSERT INTO chat_history (user_id, content, is_bot) 
                           VALUES (?, ?, ?)""",
                        (user_id, content, is_bot)
                    )
                    if not is_bot:
                        await db.execute(
                            """UPDATE users 
                               SET last_activity = datetime('now') 
                               WHERE user_id = ?""",
                            (user_id,)
                        )
                    await db.commit()
            except Exception as e:
                logging.error(f"Error adding message: {e}")
                raise

    async def get_chat_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    async with db.execute(
                        """SELECT content, is_bot, timestamp 
                           FROM chat_history 
                           WHERE user_id = ? 
                           ORDER BY timestamp DESC LIMIT ?""",
                        (user_id, limit)
                    ) as cursor:
                        rows = await cursor.fetchall()
                        return [
                            {
                                "content": row[0],
                                "is_bot": bool(row[1]),
                                "timestamp": row[2]
                            }
                            for row in reversed(rows)
                        ]
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
