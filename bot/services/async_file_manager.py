"""
Async file manager for non-blocking file I/O operations.
"""
import asyncio
import aiofiles
import aiofiles.os
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
import hashlib
from pathlib import Path


class AsyncFileManager:
    """
    Async file manager that handles file I/O operations without blocking the event loop.
    
    Features:
    - Non-blocking file writes using aiofiles
    - Background thread execution for CPU-intensive operations
    - Automatic directory creation
    - Error handling and logging
    - Performance monitoring
    """
    
    def __init__(self, max_workers: int = 2):
        """
        Initialize the async file manager.
        
        Args:
            max_workers: Maximum number of background threads for CPU-intensive operations
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="FileManager")
        self._stats = {
            "files_written": 0,
            "bytes_written": 0,
            "errors": 0,
            "background_tasks": 0
        }
        
    async def save_image_async(self, image_data: bytes, filename: str, directory: str = "data/images") -> str:
        """
        Save image data asynchronously without blocking the event loop.
        
        Args:
            image_data: Raw image bytes
            filename: Filename (without extension)
            directory: Directory to save the image
            
        Returns:
            str: Full path to the saved image
            
        Raises:
            OSError: If file operation fails
        """
        try:
            # Create full path
            file_path = os.path.join(directory, f"{filename}.jpg")
            
            # Ensure directory exists asynchronously
            await aiofiles.os.makedirs(directory, exist_ok=True)
            
            # Write file asynchronously
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(image_data)
            
            # Update statistics
            self._stats["files_written"] += 1
            self._stats["bytes_written"] += len(image_data)
            
            logging.debug(f"Saved image asynchronously: {file_path} ({len(image_data)} bytes)")
            return file_path
            
        except Exception as e:
            self._stats["errors"] += 1
            logging.error(f"Failed to save image {filename}: {e}")
            raise
    
    def save_image_background(self, image_data: bytes, filename: str, directory: str = "data/images") -> asyncio.Task:
        """
        Save image in background task without waiting for completion.
        
        Args:
            image_data: Raw image bytes
            filename: Filename (without extension)
            directory: Directory to save the image
            
        Returns:
            asyncio.Task: Background task for the save operation
        """
        self._stats["background_tasks"] += 1
        
        async def _background_save():
            try:
                return await self.save_image_async(image_data, filename, directory)
            except Exception as e:
                logging.error(f"Background image save failed for {filename}: {e}")
                return None
        
        return asyncio.create_task(_background_save())
    
    async def compute_image_hash_async(self, image_data: bytes) -> str:
        """
        Compute MD5 hash of image data in background thread to avoid blocking.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            str: MD5 hash of the image data
        """
        def _compute_hash():
            return hashlib.md5(image_data).hexdigest()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _compute_hash)
    
    async def ensure_directory_async(self, directory: str) -> None:
        """
        Ensure directory exists asynchronously.
        
        Args:
            directory: Directory path to create
        """
        try:
            await aiofiles.os.makedirs(directory, exist_ok=True)
        except Exception as e:
            logging.error(f"Failed to create directory {directory}: {e}")
            raise
    
    async def read_file_async(self, file_path: str) -> bytes:
        """
        Read file contents asynchronously.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            bytes: File contents
        """
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            
            logging.debug(f"Read file asynchronously: {file_path} ({len(content)} bytes)")
            return content
            
        except Exception as e:
            self._stats["errors"] += 1
            logging.error(f"Failed to read file {file_path}: {e}")
            raise
    
    async def file_exists_async(self, file_path: str) -> bool:
        """
        Check if file exists asynchronously.
        
        Args:
            file_path: Path to check
            
        Returns:
            bool: True if file exists
        """
        try:
            path = Path(file_path)
            return await aiofiles.os.path.exists(file_path)
        except Exception:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get file manager statistics."""
        return self._stats.copy()
    
    async def cleanup(self):
        """Clean up resources."""
        logging.info("Cleaning up async file manager...")
        
        # Shutdown the thread pool executor
        self._executor.shutdown(wait=True)
        
        logging.info("Async file manager cleaned up")


# Global async file manager instance
_file_manager = AsyncFileManager()


async def save_image_async(image_data: bytes, filename: str, directory: str = "data/images") -> str:
    """
    Save image data asynchronously.
    
    Args:
        image_data: Raw image bytes
        filename: Filename (without extension)
        directory: Directory to save the image
        
    Returns:
        str: Full path to the saved image
    """
    return await _file_manager.save_image_async(image_data, filename, directory)


def save_image_background(image_data: bytes, filename: str, directory: str = "data/images") -> asyncio.Task:
    """
    Save image in background without waiting for completion.
    
    Args:
        image_data: Raw image bytes
        filename: Filename (without extension)
        directory: Directory to save the image
        
    Returns:
        asyncio.Task: Background task for the save operation
    """
    return _file_manager.save_image_background(image_data, filename, directory)


async def compute_image_hash_async(image_data: bytes) -> str:
    """
    Compute MD5 hash of image data asynchronously.
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        str: MD5 hash of the image data
    """
    return await _file_manager.compute_image_hash_async(image_data)


def get_file_manager_stats() -> Dict[str, Any]:
    """Get file manager performance statistics."""
    return _file_manager.get_stats()


async def cleanup_file_manager():
    """Clean up file manager resources."""
    await _file_manager.cleanup()