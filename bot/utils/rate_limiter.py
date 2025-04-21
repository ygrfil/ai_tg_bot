from datetime import datetime, timedelta
import logging
from typing import Optional
import asyncio
from aiogram.types import Message
import re
import time

class MessageRateLimiter:
    def __init__(self, update_interval: float = 0.3, min_chunk_size: int = 150):
        self.last_update = 0.0
        self.update_interval = update_interval
        self.min_chunk_size = min_chunk_size
        self.last_content = ""
        self.accumulated_content = ""

    async def should_update_message(self, content: str) -> bool:
        """Determine if message should be updated based on content and timing."""
        current_time = time.time()
        time_since_last = current_time - self.last_update
        
        # Always update if enough time has passed and content is different
        if time_since_last >= self.update_interval and content != self.last_content:
            # Accumulate content
            self.accumulated_content += content[len(self.last_content):]
            
            # Check if we have enough new content
            if len(self.accumulated_content) >= self.min_chunk_size:
                self.last_update = current_time
                self.last_content = content
                self.accumulated_content = ""
                return True
                
            # Update if we have a natural break point
            if self.accumulated_content.endswith((".", "!", "?", "\n")):
                self.last_update = current_time
                self.last_content = content
                self.accumulated_content = ""
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