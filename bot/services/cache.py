from typing import Dict, Any, Optional
import time
import json
from functools import lru_cache

class CacheManager:
    def __init__(self, ttl: int = 300):  # 5 minutes default TTL
        self.ttl = ttl
        self.cache: Dict[str, tuple[Any, float]] = {}
        
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None
        
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        self.cache[key] = (value, time.time())
        
    def invalidate(self, key: str):
        if key in self.cache:
            del self.cache[key]
        
        if key.endswith('*'):
            prefix = key[:-1]
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(prefix)]
            for k in keys_to_remove:
                del self.cache[k]
            
    def build_key(self, *args) -> str:
        return ":".join(str(arg) for arg in args) 