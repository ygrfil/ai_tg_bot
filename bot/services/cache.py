from typing import Dict, Any, Optional
import time
import logging

class CacheRegion:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self.cache: Dict[str, tuple[Any, float, int]] = {}
        self.current_size = 0

class CacheManager:
    def __init__(self, default_ttl: int = 300, max_size_mb: int = 50):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.regions: Dict[str, CacheRegion] = {}
    
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
    
    def create_region(self, name: str, ttl: int = None) -> None:
        """Create a new cache region with specified TTL"""
        self.regions[name] = CacheRegion(ttl or self.default_ttl)

    async def get(self, region: str, key: str) -> Optional[Any]:
        """Get value from specified cache region"""
        if region not in self.regions:
            return None
        
        cache_region = self.regions[region]
        if key in cache_region.cache:
            value, timestamp, _ = cache_region.cache[key]
            if time.time() - timestamp < cache_region.ttl:
                return value
            self.invalidate(region, key)
        return None
    
    async def set(self, region: str, key: str, value: Any):
        """Set value in specified cache region"""
        if region not in self.regions:
            self.create_region(region)
            
        try:
            cache_region = self.regions[region]
            size = self._estimate_size(value)
            
            if size > self.max_size_bytes:
                return
            
            if cache_region.current_size + size > self.max_size_bytes:
                self._cleanup_old_entries(region, size)
            
            if cache_region.current_size + size > self.max_size_bytes:
                return
            
            if key in cache_region.cache:
                _, _, old_size = cache_region.cache[key]
                cache_region.current_size -= old_size
            
            cache_region.cache[key] = (value, time.time(), size)
            cache_region.current_size += size
            
        except Exception as e:
            logging.error(f"Error setting cache in region {region}: {e}")
    
    def invalidate(self, region: str, key: str):
        """Invalidate cache entry or pattern in specified region"""
        if region not in self.regions:
            return
            
        cache_region = self.regions[region]
        if key in cache_region.cache:
            _, _, size = cache_region.cache[key]
            cache_region.current_size -= size
            del cache_region.cache[key]
        
        if key.endswith('*'):
            prefix = key[:-1]
            keys_to_remove = [k for k in cache_region.cache.keys() if k.startswith(prefix)]
            for k in keys_to_remove:
                _, _, size = cache_region.cache[k]
                cache_region.current_size -= size
                del cache_region.cache[k]
    
    def build_key(self, *args) -> str:
        return ":".join(str(arg) for arg in args)