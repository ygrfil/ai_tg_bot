from datetime import datetime, timedelta
import logging
from typing import Optional
import asyncio
from aiogram.types import Message
import re

class MessageRateLimiter:
    def __init__(self, update_interval: float = 0.1, min_chunk_size: int = 50):
        self.update_interval = timedelta(seconds=update_interval)
        self.min_chunk_size = min_chunk_size
        self.last_update_time = datetime.min
        self.current_message = None

    async def should_update_message(self, new_content: str) -> bool:
        current_time = datetime.now()
        content_length = len(new_content)
        current_length = len(self.current_message or "")

        # Always update on first meaningful content
        if self.current_message is None and content_length > 10:
            self.last_update_time = current_time
            self.current_message = new_content
            return True
        
        # Regular update logic for subsequent updates
        if (self.current_message is not None and
            content_length >= current_length + self.min_chunk_size and 
            current_time - self.last_update_time >= self.update_interval):
            self.last_update_time = current_time
            self.current_message = new_content
            return True
        return False

    @staticmethod
    async def retry_final_update(message: Message, content: str, 
                               max_retries: int = 3, initial_delay: float = 0.3) -> None:
        """Handle final message update with retry logic"""
        # Validate content
        if not content or not content.strip():
            logging.info("Skipping update: Content is empty")
            return
        
        # Ensure content is not just HTML tags
        stripped_content = re.sub(r'<[^>]+>', '', content).strip()
        if not stripped_content:
            logging.info("Skipping update: Content contains only HTML tags")
            return

        retry_delay = initial_delay
        for attempt in range(max_retries):
            try:
                # Ensure we're sending valid content
                if len(content.strip()) > 0:
                    await message.edit_text(content, parse_mode="HTML")
                    logging.info(f"Final message update succeeded on attempt {attempt + 1}")
                else:
                    logging.info("Skipping update: Empty content after processing")
                break
            
            except Exception as e:
                error_text = str(e).lower()
                
                if "message text is empty" in error_text:
                    logging.info("Skipping update: Telegram reports empty message")
                    break
                elif "flood control" in error_text:
                    if attempt < max_retries - 1:
                        logging.warning(f"Flood control encountered. Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.1
                        continue
                elif "message is not modified" in error_text:
                    logging.debug("Message content unchanged")
                    break
                else:
                    logging.warning(f"Final message update error: {e}")
                break