import asyncio
import random
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class PollingMiddleware(BaseMiddleware):
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.current_delay = settings["backoff"]["start_delay"]
        self.failed_attempts = 0
        self.max_retries = settings["backoff"].get("max_retries", 3)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        attempt = 0
        while True:
            try:
                result = await handler(event, data)
                # Reset backoff on success
                if self.failed_attempts > 0:
                    logging.info("Connection recovered after %d attempts", self.failed_attempts)
                self.current_delay = self.settings["backoff"]["start_delay"]
                self.failed_attempts = 0
                return result
            except Exception as e:
                error_str = str(e).lower()
                is_transient = (
                    "flood control" in error_str or
                    "too many requests" in error_str or
                    "bad gateway" in error_str or
                    "timeout" in error_str or
                    "connection" in error_str
                )
                if is_transient and attempt < self.max_retries:
                    attempt += 1
                    await self.handle_rate_limit()
                    continue
                raise

    async def handle_rate_limit(self):
        """Handle rate limiting with exponential backoff and jitter"""
        self.failed_attempts += 1
        
        # Add jitter to avoid synchronization
        jitter = random.uniform(
            -self.settings["backoff"]["jitter"],
            self.settings["backoff"]["jitter"]
        )
        
        # Calculate next delay with jitter
        next_delay = min(
            self.current_delay * self.settings["backoff"]["factor"],
            self.settings["backoff"]["max_delay"]
        )
        self.current_delay = next_delay + jitter
        
        logging.warning(
            "Rate limit hit. Attempt: %d. Waiting %.2f seconds before retry...",
            self.failed_attempts,
            self.current_delay
        )
        
        await asyncio.sleep(self.current_delay)