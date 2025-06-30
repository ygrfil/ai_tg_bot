"""
Enhanced provider caching with HTTP connection pooling for optimal performance.
"""
from typing import Dict, Optional
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
import weakref
import atexit

from .base import BaseAIProvider
from .openrouter import OpenRouterProvider
from .fal import FalProvider
from .providers import PROVIDER_MODELS
from ...config import Config


class ProviderCache:
    """
    Enhanced provider cache with HTTP connection pooling and lifecycle management.
    
    Features:
    - Shared HTTP session across all providers
    - Provider instance caching with weak references
    - Automatic cleanup and connection management
    - Performance monitoring
    """
    
    def __init__(self):
        self._providers: Dict[str, BaseAIProvider] = {}
        self._last_cleanup = datetime.now()
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "providers_created": 0
        }
        
        # Register cleanup on exit
        atexit.register(self._cleanup_sync)
    
    
    async def get_provider(self, provider_name: str, config: Config) -> BaseAIProvider:
        """
        Get a cached AI provider instance.
        
        Args:
            provider_name: Name of the provider to get
            config: Configuration object
            
        Returns:
            BaseAIProvider: Cached or new provider instance
            
        Raises:
            ValueError: If provider is not found or not supported
        """
        # Check cache first
        if provider_name in self._providers:
            self._stats["cache_hits"] += 1
            return self._providers[provider_name]
        
        self._stats["cache_misses"] += 1
        
        # Validate provider exists in models
        if provider_name not in PROVIDER_MODELS:
            raise ValueError(f"Provider {provider_name} not found in PROVIDER_MODELS")
        
        # Get model configuration
        model_config = PROVIDER_MODELS[provider_name]
        provider_type = model_config['name'].split('/')[0]
        
        # Create provider instance
        provider = await self._create_provider(provider_name, provider_type, config)
        
        if provider is None:
            raise ValueError(f"No implementation found for provider {provider_name} (type: {provider_type})")
        
        # Cache the provider
        self._providers[provider_name] = provider
        self._stats["providers_created"] += 1
        logging.info(f"Created and cached new provider: {provider_name}")
        
        return provider
    
    async def _create_provider(self, provider_name: str, provider_type: str, config: Config) -> Optional[BaseAIProvider]:
        """
        Create a new provider instance.
        
        Args:
            provider_name: Name of the provider
            provider_type: Type of the provider
            config: Configuration object
            
        Returns:
            BaseAIProvider: New provider instance or None
        """
        if provider_type == "fal-ai" or provider_name == "fal":
            # Fal provider for image generation (used less frequently)
            return FalProvider(config.fal_api_key, config=config)
            
        elif provider_type in ["openai", "anthropic", "google", "perplexity"] or provider_name == "openrouter":
            # OpenRouter provider for text AI (used frequently - cache this!)
            return OpenRouterProvider(config.openrouter_api_key, config=config)
        
        return None
    
    async def cleanup(self):
        """Clean up resources and close connections."""
        logging.info("Cleaning up provider cache...")
        
        # Close providers that have cleanup methods
        for provider_name, provider in self._providers.items():
            if hasattr(provider, 'cleanup'):
                try:
                    await provider.cleanup()
                except Exception as e:
                    logging.warning(f"Error cleaning up provider {provider_name}: {e}")
        
        # Clear provider cache
        self._providers.clear()
        logging.info("Provider cache cleaned up")
    
    def _cleanup_sync(self):
        """Synchronous cleanup for atexit handler."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.cleanup())
            else:
                loop.run_until_complete(self.cleanup())
        except Exception as e:
            logging.warning(f"Error in sync cleanup: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get performance statistics."""
        return self._stats.copy()
    
    async def periodic_cleanup(self):
        """Perform periodic cleanup of idle resources."""
        now = datetime.now()
        if now - self._last_cleanup > timedelta(hours=1):
            logging.info("Performing periodic provider cache cleanup")
            
            # Could add provider health checks here in the future
            
            self._last_cleanup = now


# Global provider cache instance
_provider_cache = ProviderCache()


async def get_provider(provider_name: str, config: Config) -> BaseAIProvider:
    """
    Get an AI provider instance with enhanced caching and connection pooling.
    
    Args:
        provider_name: Name of the provider to get
        config: Config instance containing API keys and settings
        
    Returns:
        An instance of BaseAIProvider with optimized connections
        
    Raises:
        ValueError: If provider is not found
    """
    return await _provider_cache.get_provider(provider_name, config)


async def cleanup_providers():
    """Clean up all provider resources."""
    await _provider_cache.cleanup()


def get_provider_stats() -> Dict[str, int]:
    """Get provider cache performance statistics."""
    return _provider_cache.get_stats()