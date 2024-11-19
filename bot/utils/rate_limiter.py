from datetime import datetime, timedelta
import logging
from typing import Optional
import asyncio
from aiogram.types import Message

class MessageRateLimiter:
    def __init__(self, 
                 update_interval: int = 0.35,
                 typing_interval: int = 0.5,
                 min_chunk_size: int = 200):
        self.update_interval = timedelta(seconds=update_interval)
        self.typing_interval = timedelta(seconds=typing_interval)
        self.min_chunk_size = min_chunk_size
        self.last_update_time = datetime.now()
        self.last_typing_time = datetime.now()
        self.current_message: Optional[str] = None

    async def should_update_typing(self) -> bool:
        current_time = datetime.now()
        if current_time - self.last_typing_time >= self.typing_interval:
            self.last_typing_time = current_time
            return True
        return False

    async def should_update_message(self, new_content: str) -> bool:
        current_time = datetime.now()
        if (self.current_message is None or
            (len(new_content) >= len(self.current_message or "") + self.min_chunk_size and 
             current_time - self.last_update_time >= self.update_interval)):
            self.last_update_time = current_time
            self.current_message = new_content
            return True
        return False

    async def handle_typing(self, message: Message) -> None:
        """Handle typing indicator with rate limiting"""
        try:
            if await self.should_update_typing():
                await message.bot.send_chat_action(message.chat.id, "typing")
        except Exception as e:
            if "flood control" not in str(e).lower():
                logging.warning(f"Typing indicator error (non-critical): {e}")

    @staticmethod
    async def retry_final_update(message: Message, content: str, 
                               max_retries: int = 3, initial_delay: int = 2) -> None:
        """Handle final message update with retry logic"""
        retry_delay = initial_delay
        for attempt in range(max_retries):
            try:
                await message.edit_text(content, parse_mode="HTML")
                break
            except Exception as e:
                if "flood control" in str(e).lower():
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                elif "message is not modified" not in str(e).lower():
                    logging.warning(f"Final message update error (non-critical): {e}")
                break 