from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import aiosqlite
import os
from functools import wraps
import logging
import asyncio
from contextlib import asynccontextmanager
import json
from collections import deque
from .cache import CacheManager
from .async_file_manager import save_image_background, compute_image_hash_async, AsyncFileManager
import hashlib
import re

class DatabasePool:
    def __init__(self, db_path: str, max_connections: int = 10, min_connections: int = 2):
        self.db_path = db_path
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.pool = deque()
        self.lock = asyncio.Lock()
        self._condition = asyncio.Condition(self.lock)
        self._creating = 0
        self._active = 0
        self._last_cleanup = 0
        self.stats = {"hits": 0, "misses": 0, "timeouts": 0}

    async def initialize(self):
        """Pre-initialize minimum connections"""
        for _ in range(self.min_connections):
            db = await self._create_connection()
            self.pool.append(db)

    async def acquire(self, timeout: float = 5.0):
        need_create = False
        while True:
            async with self._condition:
                # Wait for a connection to become available or capacity to create a new one
                try:
                    await asyncio.wait_for(
                        self._condition.wait_for(
                            lambda: bool(self.pool) or (self._creating + self._active < self.max_connections)
                        ),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    self.stats["timeouts"] += 1
                    raise TimeoutError("Connection pool timeout")

                # Try to get existing connection first
                if self.pool:
                    self.stats["hits"] += 1
                    conn = self.pool.popleft()
                    self._active += 1
                    return conn

                # Create new connection if under limit
                if self._creating + self._active < self.max_connections:
                    self._creating += 1
                    self.stats["misses"] += 1
                    need_create = True
                else:
                    # Should not happen due to wait_for, but guard anyway
                    self.stats["timeouts"] += 1
                    raise TimeoutError("Connection pool exhausted")

            # Create connection OUTSIDE the lock
            if need_create:
                try:
                    db = await self._create_connection()
                    async with self._condition:
                        self._creating -= 1
                        self._active += 1
                    return db
                except Exception:
                    async with self._condition:
                        self._creating -= 1
                        self._condition.notify_all()  # Wake up other waiters
                    raise

    async def release(self, db):
        to_close = []
        async with self._condition:
            self._active -= 1
            current_time = asyncio.get_event_loop().time()

            # Collect idle connections to close WITHOUT awaiting while holding the lock
            if current_time - self._last_cleanup > 60:  # Every minute
                while len(self.pool) > self.min_connections:
                    idle_conn = self.pool.pop()
                    to_close.append(idle_conn)
                self._last_cleanup = current_time

            # Return provided connection to pool
            self.pool.append(db)
            # Notify one waiter that a connection is available
            self._condition.notify()

        # Perform connection closes outside the lock to avoid blocking other waiters
        for conn in to_close:
            try:
                await conn.close()
            except Exception as e:
                logging.warning(f"Error closing idle DB connection: {e}")

    async def _create_connection(self):
        db = await aiosqlite.connect(self.db_path)
        await self._optimize_db_settings(db)
        return db

    @staticmethod
    async def _optimize_db_settings(db):
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=-64000")  # 64MB cache
        await db.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        await db.execute("PRAGMA page_size=4096")
        await db.execute("PRAGMA temp_store=MEMORY")
        await db.execute("PRAGMA busy_timeout=5000")  # 5 second timeout

def with_retries(max_retries=3, base_delay=0.1):
    """Decorator for automatic retry with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logging.warning(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        await asyncio.sleep(delay)
            raise last_error
        return wrapper
    return decorator

class Storage:
    def __init__(self, db_path: str = "data/chat.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.pool = DatabasePool(db_path, max_connections=10)
        self._lock = asyncio.Lock()
        self.cache = CacheManager(default_ttl=300, max_size_mb=100)
        self._batch_size = 50
        self._initialize_cache()
        self._initialized = False

    async def _ensure_pool_initialized(self):
        """Ensure database pool is initialized"""
        # Use a lock to prevent race condition during pool initialization
        if not hasattr(self, '_pool_init_lock'):
            self._pool_init_lock = asyncio.Lock()
        
        if not hasattr(self.pool, '_initialized'):
            async with self._pool_init_lock:
                # Double-check inside the lock
                if not hasattr(self.pool, '_initialized'):
                    await self.pool.initialize()
                    self.pool._initialized = True

    def _initialize_cache(self):
        """Initialize cache regions with specific TTLs"""
        self.cache.create_region('user_settings', ttl=300)   # 5 minutes for user settings
        self.cache.create_region('chat_history', ttl=60)     # 1 minute for chat history
        self.cache.create_region('usage_stats', ttl=600)     # 10 minutes for stats
        self.cache.create_region('images', ttl=1800)         # 30 minutes for images

    async def process_users_batch(self, users: List[int], processor_func, batch_size: int = None) -> List[Any]:
        """Process users in batches to avoid overwhelming the database"""
        batch_size = batch_size or self._batch_size
        results = []
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[processor_func(user_id) for user_id in batch],
                return_exceptions=True
            )
            results.extend([r for r in batch_results if not isinstance(r, Exception)])
        return results

    @asynccontextmanager
    async def _db_connect(self):
        db = await self.pool.acquire()
        try:
            yield db
        finally:
            await self.pool.release(db)

    @with_retries(max_retries=3)
    async def get_chat_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent chat history for context - optimized single query"""
        await self.ensure_initialized()
        
        try:
            async with self._db_connect() as db:
                # Optimized: Single query that gets messages and checks age
                async with db.execute("""
                    SELECT content, is_bot, timestamp,
                           (julianday('now') - julianday(timestamp)) * 24 as hours_ago
                    FROM (
                        SELECT content, is_bot, timestamp
                        FROM chat_history
                        WHERE user_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ) sub
                    ORDER BY timestamp ASC
                """, (user_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    if not rows:
                        return []
                    
                    # Check if oldest message is too old (>2 hours)
                    # If so, clear history in background
                    if rows[-1][3] > 2:  # hours_ago > 2
                        asyncio.create_task(self.clear_user_history(user_id))
                        return []

                    # Convert to list of messages (already in chronological order)
                    result = [
                        {
                            "content": row[0],
                            "is_bot": bool(row[1]),
                            "timestamp": row[2]
                        }
                        for row in rows
                    ]
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
        """Add message to history with optimized storage and try to extract user name"""
        try:
            content_str = str(content).strip() if content else ""
        
            async with self._db_connect() as db:
                if image_data:
                    await db.execute("""
                        UPDATE chat_history 
                        SET content = REPLACE(content, '[Image:', '[Old Image:')
                        WHERE user_id = ? AND content LIKE '%[Image:%'
                    """, (user_id,))
                    
                    # Compute hash asynchronously to avoid blocking
                    image_hash = await compute_image_hash_async(image_data)
                    
                    # Start image saving in background - don't wait for completion
                    save_image_background(image_data, image_hash, "data/images")
                    
                    content_str = f"{content_str}\n[Image: {image_hash}]"
            
                await db.execute("""
                    INSERT INTO chat_history (
                        user_id,
                        content,
                        is_bot,
                        timestamp
                    ) VALUES (
                        ?, ?, ?,
                        datetime('now')
                    )
                """, (user_id, content_str, 1 if is_bot else 0))
                await db.commit()
                
                # Simplified name extraction - only for direct introductions
                if not is_bot and not content_str.startswith('/'):
                    # Only check first few messages for self-introductions
                    intro_patterns = [
                        r"(?:I am|I'm|my name is|call me) ([A-Z][a-z]+)",
                        r"(?:Hello|Hi)(?:,|!) (?:I am|I'm) ([A-Z][a-z]+)"
                    ]
                    
                    for pattern in intro_patterns:
                        match = re.search(pattern, content_str)
                        if match:
                            possible_name = match.group(1).strip()
                            if 2 < len(possible_name) < 20:
                                await db.execute("""
                                    UPDATE users
                                    SET first_name = ?
                                    WHERE user_id = ? AND (first_name IS NULL OR first_name = '')
                                """, (possible_name, user_id))
                                await db.commit()
                                break

                # Invalidate the chat history cache for this user
                cache_key = f"history_{user_id}"
                await self.cache.set('chat_history', cache_key, None)
        except Exception as e:
            logging.error(f"Error adding to chat history: {e}", exc_info=True)
            raise

    async def clear_user_history(self, user_id: int) -> None:
        """Clear user history and invalidate cache"""
        try:
            # Delete messages from DB
            async with self._db_connect() as db:
                await db.execute(
                    "DELETE FROM chat_history WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()

            # Invalidate cache for this user
            cache_key = f"history_{user_id}"
            await self.cache.set('chat_history', cache_key, None)
        except Exception as e:
            logging.error(f"Error clearing user history: {e}")
            raise

    async def get_user_settings(self, user_id: int) -> Optional[dict]:
        """Get user settings with caching"""
        await self.ensure_initialized()
        
        # Check cache first for faster response
        cache_key = f"settings_{user_id}"
        cached = await self.cache.get('user_settings', cache_key)
        if cached is not None:
            return cached
        
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT settings, current_provider, current_model
                    FROM users
                    WHERE user_id = ?
                """, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        import json
                        settings = json.loads(row[0]) if row[0] else {}
                        if row[1]:
                            settings['current_provider'] = row[1]
                        if row[2]:
                            settings['current_model'] = row[2]
                        
                        # Cache for 5 minutes
                        await self.cache.set('user_settings', cache_key, settings)
                        return settings
                    return None
        except Exception as e:
            logging.error(f"Error getting user settings: {e}")
            return None

    async def ensure_initialized(self):
        """Initialize the database with all required tables"""
        # Double-check pattern to prevent race condition
        if self._initialized:
            return

        async with self._lock:
            # Check again inside the lock
            if self._initialized:
                return
            
            try:
                await self._ensure_pool_initialized()
                async with self._db_connect() as db:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            first_name TEXT,
                            current_provider TEXT,
                            current_model TEXT,
                            settings TEXT DEFAULT '{}',
                            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

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

                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS access_requests (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            username TEXT,
                            first_name TEXT,
                            last_name TEXT,
                            request_message TEXT,
                            status TEXT DEFAULT 'pending',
                            request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            admin_response_timestamp TIMESTAMP,
                            admin_id INTEGER
                        )
                    """)

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
                    await db.execute("""
                        CREATE INDEX IF NOT EXISTS idx_access_requests_status
                        ON access_requests(status, request_timestamp DESC)
                    """)

                    # Create images directory asynchronously
                    file_manager = AsyncFileManager()
                    await file_manager.ensure_directory_async("data/images")

                    await db.commit()
                    self._initialized = True

            except Exception as e:
                logging.error(f"Database initialization error: {e}", exc_info=True)
                raise

    @with_retries(max_retries=3)
    async def save_user_settings(self, user_id: int, settings: dict):
        """Save user settings to database and invalidate cache"""
        await self.ensure_initialized()
        async with self._lock:
            try:
                async with self._db_connect() as db:
                    await db.execute("""
                        INSERT INTO users (user_id, settings, current_provider, current_model, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(user_id) DO UPDATE SET
                            settings = excluded.settings,
                            current_provider = excluded.current_provider,
                            current_model = excluded.current_model,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        user_id,
                        json.dumps(settings),
                        settings.get('current_provider'),
                        settings.get('current_model')
                    ))
                    await db.commit()
                    
                # Invalidate cache after save
                cache_key = f"settings_{user_id}"
                self.cache.invalidate('user_settings', cache_key)
            except Exception as e:
                logging.error(f"Error saving user settings: {e}", exc_info=True)
                raise

    @with_retries(max_retries=3)
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
                logging.error(f"Error ensuring user exists: {e}", exc_info=True)
                raise

    @with_retries(max_retries=2)  # Fewer retries for logging since it's not critical
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
            # Don't raise for logging errors - they're not critical
            logging.error(f"Error logging usage stats: {e}", exc_info=True)

    async def get_usage_stats(self, period: str = 'month') -> Dict[str, Any]:
        """Get usage statistics for all users"""
        try:
            async with self._db_connect() as db:
                async with db.execute("SELECT COUNT(DISTINCT user_id) FROM users") as cursor:
                    total_users = (await cursor.fetchone())[0]

                async with db.execute("""
                    SELECT COUNT(DISTINCT user_id) FROM users 
                    WHERE datetime(last_activity) > datetime('now', '-1 day')
                """) as cursor:
                    active_users_24h = (await cursor.fetchone())[0]

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

    async def get_all_users(self) -> List[Tuple[int, str]]:
        """Get all user IDs and usernames from the database."""
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT user_id, username 
                    FROM users
                """) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting all users: {e}")
            return []

    async def get_user_display_name(self, user_id: int) -> str:
        """Get a user's display name from the database"""
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT username, first_name
                    FROM users
                    WHERE user_id = ?
                """, (user_id,)) as cursor:
                    user_info = await cursor.fetchone()
                    
                    if user_info:
                        username, first_name = user_info
                        display_parts = []
                        
                        if username:
                            display_parts.append(f"@{username}")
                        if first_name:
                            display_parts.append(first_name)
                            
                        if display_parts:
                            return " | ".join(display_parts)
                        else:
                            return f"User {user_id}"
                    else:
                        return f"User {user_id}"
        except Exception as e:
            logging.error(f"Error getting user display name: {e}")
            return f"User {user_id}"

    async def can_request_access(self, user_id: int) -> bool:
        """Check if user can make an access request (1 per 24 hours)."""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT id FROM access_requests 
                    WHERE user_id = ? 
                    AND date(request_timestamp) = date('now')
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result is None
        except Exception as e:
            logging.error(f"Error checking access request eligibility: {e}")
            return False

    async def submit_access_request(
        self, 
        user_id: int, 
        username: str = None, 
        first_name: str = None, 
        last_name: str = None, 
        message: str = None
    ) -> bool:
        """Submit an access request."""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                await db.execute("""
                    INSERT INTO access_requests (
                        user_id, username, first_name, last_name, request_message
                    ) VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, message))
                await db.commit()
                return True
        except Exception as e:
            logging.error(f"Error submitting access request: {e}")
            return False

    async def get_pending_access_requests(self) -> List[Dict[str, Any]]:
        """Get all pending access requests."""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                async with db.execute("""
                    SELECT id, user_id, username, first_name, last_name, 
                           request_message, request_timestamp
                    FROM access_requests 
                    WHERE status = 'pending'
                    ORDER BY request_timestamp ASC
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            "id": row[0],
                            "user_id": row[1],
                            "username": row[2],
                            "first_name": row[3],
                            "last_name": row[4],
                            "request_message": row[5],
                            "request_timestamp": row[6]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logging.error(f"Error getting pending access requests: {e}")
            return []

    async def approve_access_request(self, request_id: int, admin_id: int) -> bool:
        """Approve an access request and add user to allowed list."""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                # Get request details
                async with db.execute("""
                    SELECT user_id, username, first_name FROM access_requests 
                    WHERE id = ? AND status = 'pending'
                """, (request_id,)) as cursor:
                    request = await cursor.fetchone()
                    
                if not request:
                    return False
                
                user_id, username, first_name = request
                
                # Update request status
                await db.execute("""
                    UPDATE access_requests 
                    SET status = 'approved', admin_response_timestamp = CURRENT_TIMESTAMP, admin_id = ?
                    WHERE id = ?
                """, (admin_id, request_id))
                
                # Ensure user exists in users table
                await db.execute("""
                    INSERT OR REPLACE INTO users (user_id, username, first_name, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, username, first_name))
                
                await db.commit()
                return True
        except Exception as e:
            logging.error(f"Error approving access request: {e}")
            return False

    async def reject_access_request(self, request_id: int, admin_id: int) -> bool:
        """Reject an access request."""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                await db.execute("""
                    UPDATE access_requests 
                    SET status = 'rejected', admin_response_timestamp = CURRENT_TIMESTAMP, admin_id = ?
                    WHERE id = ? AND status = 'pending'
                """, (admin_id, request_id))
                await db.commit()
                return True
        except Exception as e:
            logging.error(f"Error rejecting access request: {e}")
            return False

    async def get_access_request_stats(self) -> Dict[str, Any]:
        """Get access request statistics."""
        await self.ensure_initialized()
        try:
            async with self._db_connect() as db:
                stats = {}
                
                # Count pending requests
                async with db.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'") as cursor:
                    stats['pending'] = (await cursor.fetchone())[0]
                
                # Count total requests today
                async with db.execute("""
                    SELECT COUNT(*) FROM access_requests 
                    WHERE date(request_timestamp) = date('now')
                """) as cursor:
                    stats['today'] = (await cursor.fetchone())[0]
                
                # Count approved this week
                async with db.execute("""
                    SELECT COUNT(*) FROM access_requests 
                    WHERE status = 'approved' 
                    AND request_timestamp >= date('now', '-7 days')
                """) as cursor:
                    stats['approved_this_week'] = (await cursor.fetchone())[0]
                
                return stats
        except Exception as e:
            logging.error(f"Error getting access request stats: {e}")
            return {"pending": 0, "today": 0, "approved_this_week": 0}
