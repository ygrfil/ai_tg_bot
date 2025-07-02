from typing import Dict, Any, Optional
from collections import OrderedDict
import time
import logging

class CacheRegion:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        # Use OrderedDict for O(1) LRU operations - maintains insertion/access order
        self.cache: OrderedDict[str, tuple[Any, float, int]] = OrderedDict()
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
    
    def _cleanup_old_entries(self, cache_region: 'CacheRegion', required_space: int):
        """Remove old entries to free up space using efficient LRU eviction"""
        # OrderedDict maintains order - oldest accessed items are at the beginning
        while (cache_region.current_size + required_space > self.max_size_bytes and 
               cache_region.cache):
            # O(1) removal of least recently used item
            key, (_, _, size) = cache_region.cache.popitem(last=False)
            cache_region.current_size -= size
            logging.debug(f"Evicted cache entry: {key}, freed {size} bytes")
    
    def create_region(self, name: str, ttl: int = None) -> None:
        """Create a new cache region with specified TTL"""
        self.regions[name] = CacheRegion(ttl or self.default_ttl)

    async def get(self, region: str, key: str) -> Optional[Any]:
        """Get value from specified cache region with LRU access tracking"""
        if region not in self.regions:
            return None
        
        cache_region = self.regions[region]
        if key in cache_region.cache:
            value, timestamp, size = cache_region.cache[key]
            if time.time() - timestamp < cache_region.ttl:
                # Move to end for LRU tracking - O(1) operation
                cache_region.cache.move_to_end(key)
                return value
            else:
                # Remove expired entry
                del cache_region.cache[key]
                cache_region.current_size -= size
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
                self._cleanup_old_entries(cache_region, size)
            
            if cache_region.current_size + size > self.max_size_bytes:
                logging.warning(f"Cannot cache item in region {region}: exceeds max size after cleanup")
                return
            
            if key in cache_region.cache:
                _, _, old_size = cache_region.cache[key]
                cache_region.current_size -= old_size
            
            # Store the value and update size
            cache_region.cache[key] = (value, time.time(), size)
            cache_region.current_size += size
            
            # Move to end for LRU tracking (most recently set)
            cache_region.cache.move_to_end(key)
            
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        total_size = 0
        total_entries = 0
        region_stats = {}
        
        for region_name, region in self.regions.items():
            region_stats[region_name] = {
                "entries": len(region.cache),
                "size_bytes": region.current_size,
                "size_mb": round(region.current_size / (1024 * 1024), 2),
                "ttl": region.ttl
            }
            total_size += region.current_size
            total_entries += len(region.cache)
        
        return {
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_size_mb": round(self.max_size_bytes / (1024 * 1024), 2),
            "utilization_percent": round((total_size / self.max_size_bytes) * 100, 1),
            "regions": region_stats
        }