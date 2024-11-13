from typing import Dict, Any, List, Optional
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
        """Initialize database without default values"""
        if self._initialized:
            return

        async with self._lock:
            try:
                async with self._db_connect() as db:
                    # Create users table
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY,
                            current_provider TEXT NULL,
                            current_model TEXT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    # Create chat history table
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS chat_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            content TEXT,
                            is_bot BOOLEAN,
                            image_data BLOB NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id)
                        )
                    """)
                    
                    await db.commit()
                    self._initialized = True
            except Exception as e:
                logging.error(f"Error initializing database: {e}")
                raise

    async def _init_db(self):
        """Initialize the database with required tables."""
        async with self._lock:
            async with self._db_connect() as db:
                # Create users table with all necessary columns
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        current_provider TEXT DEFAULT 'openai',
                        current_model TEXT DEFAULT 'gpt-4o',
                        settings TEXT,
                        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create chat_history table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        is_bot BOOLEAN NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        image_data BLOB,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                """)
                await db.commit()

    async def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user settings without defaults"""
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    async with db.execute(
                        """SELECT current_provider, current_model 
                           FROM users 
                           WHERE user_id = ?""",
                        (user_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row and row[0] and row[1]:  # Only return if both provider and model are set
                            return {
                                "current_provider": row[0],
                                "current_model": row[1]
                            }
                        return None
            except Exception as e:
                logging.error(f"Error getting user settings: {e}")
                return None

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
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    async with db.execute("""
                        SELECT content, is_bot, image_data, timestamp
                        FROM chat_history
                        WHERE user_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (user_id, limit)) as cursor:
                        rows = await cursor.fetchall()
                    
                    history = []
                    for row in reversed(rows):  # Maintain chronological order
                        entry = {
                            "content": row[0],
                            "is_bot": row[1],
                            "image": row[2],  # Include image data directly
                            "timestamp": row[3]
                        }
                        history.append(entry)
                    
                    return history
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

    async def ensure_user_exists(self, user_id: int):
        """Ensure user exists in database without any defaults"""
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    await db.execute(
                        """INSERT OR IGNORE INTO users 
                           (user_id) 
                           VALUES (?)""",
                        (user_id,)
                    )
                    await db.commit()
            except Exception as e:
                logging.error(f"Error ensuring user exists: {e}")
                raise
