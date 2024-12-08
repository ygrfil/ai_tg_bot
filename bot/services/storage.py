from typing import Dict, Any, List, Optional
from datetime import datetime
import aiosqlite
import os
import logging
import asyncio
from contextlib import asynccontextmanager
import json
from collections import deque
from .cache import CacheManager  # Assuming cache.py is created
import hashlib

class DatabasePool:
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self.pool = deque()
        self.lock = asyncio.Lock()
        self._creating = 0

    async def acquire(self):
        async with self.lock:
            while True:
                if self.pool:
                    return self.pool.popleft()
                if self._creating < self.max_connections:
                    self._creating += 1
                    break
                await asyncio.sleep(0.1)

        try:
            db = await aiosqlite.connect(self.db_path)
            await self._optimize_db_settings(db)
            return db
        finally:
            self._creating -= 1

    async def release(self, db):
        async with self.lock:
            self.pool.append(db)

    @staticmethod
    async def _optimize_db_settings(db):
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=-64000")  # 64MB cache
        await db.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        await db.execute("PRAGMA page_size=4096")
        await db.execute("PRAGMA temp_store=MEMORY")

class Storage:
    def __init__(self, db_path: str = "data/chat.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.pool = DatabasePool(db_path)
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def _db_connect(self):
        db = await self.pool.acquire()
        try:
            yield db
        finally:
            await self.pool.release(db)

    async def get_chat_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get chat history with optimized retrieval"""
        try:
            async with self._db_connect() as db:
                # Get all recent messages in chronological order
                async with db.execute("""
                    WITH LastMessages AS (
                        SELECT 
                            content,
                            is_bot,
                            timestamp,
                            ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn
                        FROM chat_history
                        WHERE user_id = ?
                    )
                    SELECT 
                        content,
                        is_bot,
                        timestamp
                    FROM LastMessages
                    WHERE rn <= ?  -- Take last N messages
                    ORDER BY timestamp ASC
                """, (user_id, limit * 2)) as cursor:  # Double limit to include both user and bot messages
                    rows = await cursor.fetchall()
            
                result = []
                for row in rows:
                    message = {
                        "content": row[0],
                        "is_bot": bool(row[1]),
                        "timestamp": row[2]
                    }
                    result.append(message)
            
                return result
            
        except Exception as e:
            logging.error(f"Error getting chat history: {e}", exc_info=True)
            return []

    async def add_to_history(
        self,
        user_id: int,
        content: str,
        is_bot: bool,
        image_data: Optional[bytes] = None
    ) -> None:
        """Add message to history with optimized storage"""
        try:
            content_str = str(content).strip() if content else ""
        
            async with self._db_connect() as db:
                if image_data:
                    # Only store latest image
                    await db.execute("""
                        UPDATE chat_history 
                        SET content = REPLACE(content, '[Image:', '[Old Image:')
                        WHERE user_id = ? AND content LIKE '%[Image:%'
                    """, (user_id,))
                
                    # Store image reference instead of full data
                    image_hash = hashlib.md5(image_data).hexdigest()
                    image_path = f"data/images/{image_hash}.jpg"
                    os.makedirs(os.path.dirname(image_path), exist_ok=True)
                    with open(image_path, "wb") as f:
                        f.write(image_data)
                    content_str = f"{content_str}\n[Image: {image_hash}]"
            
                # Add message with precise timestamp
                await db.execute("""
                    INSERT INTO chat_history (
                        user_id, 
                        content, 
                        is_bot, 
                        timestamp
                    ) VALUES (
                        ?, ?, ?, 
                        strftime('%Y-%m-%d %H:%M:%f', 'now')
                    )
                """, (user_id, content_str, 1 if is_bot else 0))

                await db.commit()
            
        except Exception as e:
            logging.error(f"Error adding to chat history: {e}", exc_info=True)
            raise

    async def clear_user_history(self, user_id: int):
        """Clear user history"""
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

    async def get_user_settings(self, user_id: int) -> Optional[dict]:
        """Get user settings"""
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
                        settings.update({
                            'current_provider': row[1],
                            'current_model': row[2]
                        })
                        return settings
                    return None
        except Exception as e:
            logging.error(f"Error getting user settings: {e}")
            return None

    async def ensure_initialized(self):
        """Initialize the database with all required tables"""
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    # Create users table first
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            first_name TEXT,
                            current_provider TEXT,
                            current_model TEXT,
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
                            is_bot BOOLEAN,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id)
                        )
                    """)

                    # Create usage_stats table
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS usage_stats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            provider TEXT NOT NULL,
                            model TEXT NOT NULL DEFAULT 'unknown',
                            message_count INTEGER DEFAULT 1,
                            token_count INTEGER DEFAULT 0,
                            image_count INTEGER DEFAULT 0,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id)
                        )
                    """)

                    # Create indices
                    await db.execute("""
                        CREATE INDEX IF NOT EXISTS idx_chat_history_user_id_timestamp 
                        ON chat_history(user_id, timestamp DESC)
                    """)
                    await db.execute("""
                        CREATE INDEX IF NOT EXISTS idx_usage_stats_combined
                        ON usage_stats(user_id, provider, timestamp)
                    """)
                    await db.execute("""
                        CREATE INDEX IF NOT EXISTS idx_users_settings
                        ON users(user_id, current_provider, current_model)
                    """)

                    # Create images directory
                    os.makedirs("data/images", exist_ok=True)

                    await db.commit()

            except Exception as e:
                logging.error(f"Database initialization error: {e}", exc_info=True)
                raise

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
                        """INSERT INTO chat_history (user_id, content, is_bot) 
                           VALUES (?, ?, ?)""",
                        (user_id, content, is_bot)
                    )
                    await db.commit()
            except Exception as e:
                logging.error(f"Error adding message: {e}")
                raise
    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """Get user data from the database"""
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT 
                        user_id,
                        username,
                        current_provider,
                        current_model,
                        settings,
                        last_activity
                    FROM users 
                    WHERE user_id = ?
                """, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return {
                            "user_id": row[0],
                            "username": row[1],
                            "current_provider": row[2],  # Default to claude if None
                            "current_model": row[3],  # Default model
                            "settings": row[4],
                            "last_activity": row[5]
                        }
                    
                    # If user doesn't exist, create new user with default settings
                    await db.execute("""
                        INSERT INTO users (
                            user_id, 
                            current_provider,
                            current_model,
                            settings
                        ) VALUES (?, '{}')
                    """, (user_id,))
                    await db.commit()
                    
                    return {
                        "user_id": user_id,
                        "username": None,
                        "current_provider": None,  # Default provider with no value
                        "current_model": None,      # Default model with no value
                        "settings": "{}",
                        "last_activity": None
                    }
                    
        except Exception as e:
            logging.error(f"Error getting user data: {e}")
            # Return default values if there's an error
            return {
                "user_id": user_id,
                "username": None,
                "current_provider": None,
                "current_model": None,
                "settings": "{}",
                "last_activity": None
            }

    async def ensure_user_exists(self, user_id: int, username: str = None, first_name: str = None):
        """Ensure user exists in database and update user info"""
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    if username or first_name:
                        await db.execute("""
                            INSERT INTO users (user_id, username, first_name) 
                            VALUES (?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET 
                                username = COALESCE(?, users.username),
                                first_name = COALESCE(?, users.first_name),
                                updated_at = CURRENT_TIMESTAMP
                        """, (user_id, username, first_name, username, first_name))
                    else:
                        await db.execute("""
                            INSERT OR IGNORE INTO users (user_id) 
                            VALUES (?)
                        """, (user_id,))
                    await db.commit()
            except Exception as e:
                logging.error(f"Error ensuring user exists: {e}")
                raise

    async def log_usage(
        self,
        user_id: int,
        provider: str,
        model: str,
        tokens: int = 0,
        has_image: bool = False
    ) -> None:
        """Log usage statistics for a user"""
        try:
            async with self._db_connect() as db:
                await db.execute("""
                    INSERT INTO usage_stats (
                        user_id,
                        provider,
                        model,
                        message_count,
                        token_count,
                        image_count,
                        timestamp
                    ) VALUES (?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, provider, model, tokens, 1 if has_image else 0))
                await db.commit()
        except Exception as e:
            logging.error(f"Error logging usage stats: {e}")

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
