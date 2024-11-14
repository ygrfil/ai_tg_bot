from typing import Dict, Any, Optional
import time
import logging

class CacheManager:
    def __init__(self, max_size_mb: int = 50):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache: Dict[str, tuple[Any, float, int]] = {}
        self.current_size = 0
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate size of cached value in bytes"""
        try:
            if isinstance(value, list):
                total_size = 0
                for item in value:
                    content_size = len(str(item.get('content', '')).encode('utf-8'))
                    total_size += content_size
                    
                    if 'image' in item and item['image'] is not None:
                        total_size += len(item['image'])
                    
                return total_size
            return len(str(value).encode('utf-8'))
        except Exception as e:
            logging.error(f"Error estimating cache size: {e}")
            return 0
    
    def _cleanup_old_entries(self, required_space: int):
        """Remove old entries to free up space"""
        sorted_items = sorted(self.cache.items(), key=lambda x: x[1][1])
        
        for key, (_, _, size) in sorted_items:
            if self.current_size + required_space <= self.max_size_bytes:
                break
            self.current_size -= size
            del self.cache[key]
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, timestamp, _ = self.cache[key]
            if time.time() - timestamp < 300:  # 5 minutes TTL
                return value
            self.invalidate(key)
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        try:
            size = self._estimate_size(value)
            
            if size > self.max_size_bytes:
                return
            
            if self.current_size + size > self.max_size_bytes:
                self._cleanup_old_entries(size)
            
            if self.current_size + size > self.max_size_bytes:
                return
            
            if key in self.cache:
                _, _, old_size = self.cache[key]
                self.current_size -= old_size
            
            self.cache[key] = (value, time.time(), size)
            self.current_size += size
            
        except Exception as e:
            logging.error(f"Error setting cache: {e}")
    
    def invalidate(self, key: str):
        if key in self.cache:
            _, _, size = self.cache[key]
            self.current_size -= size
            del self.cache[key]
        
        if key.endswith('*'):
            prefix = key[:-1]
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(prefix)]
            for k in keys_to_remove:
                _, _, size = self.cache[k]
                self.current_size -= size
                del self.cache[k]
    
    def build_key(self, *args) -> str:
        return ":".join(str(arg) for arg in args)