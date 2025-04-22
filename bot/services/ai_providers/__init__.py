from typing import Dict, Optional, Type
from .base import BaseAIProvider
from .openrouter import OpenRouterProvider
from .fal import FalProvider
from ...config import Config
from .providers import PROVIDER_MODELS
import logging

__all__ = ['get_provider']

# Provider instance cache to maintain state
_provider_instances: Dict[str, BaseAIProvider] = {}

def get_provider(provider_name: str, config: Config) -> BaseAIProvider:
    """
    Get an AI provider instance based on the provider name.
    Uses a singleton pattern to maintain provider state.
    
    Args:
        provider_name: Name of the provider to get
        config: Config instance containing API keys and settings
        
    Returns:
        An instance of BaseAIProvider
        
    Raises:
        ValueError: If provider is not found
    """
    global _provider_instances
    
    # Check if we already have an instance for this provider
    if provider_name in _provider_instances:
        logging.debug(f"Using existing provider instance for {provider_name}")
        return _provider_instances[provider_name]
    
    # First check if the provider exists in our models
    if provider_name not in PROVIDER_MODELS:
        raise ValueError(f"Provider {provider_name} not found in PROVIDER_MODELS")
    
    # Get the actual provider name from the model config
    model_config = PROVIDER_MODELS[provider_name]
    provider_type = model_config['name'].split('/')[0]  # e.g., 'openai' from 'openai/gpt-4'
    
    provider: Optional[BaseAIProvider] = None
    
    # Map provider types to their implementations
    if provider_type == "fal-ai" or provider_name == "fal":
        provider = FalProvider(config.fal_api_key, config=config)
    elif provider_type in ["openai", "anthropic", "google", "perplexity"] or provider_name == "openrouter":
        provider = OpenRouterProvider(config.openrouter_api_key, config=config)
    
    if provider is None:
        raise ValueError(f"No implementation found for provider {provider_name} (type: {provider_type})")
    
    # Cache the provider instance
    _provider_instances[provider_name] = provider
    logging.info(f"Created and cached new provider instance for {provider_name}")
    
    return provider

def clear_provider_instances():
    """Clear all provider instances from the cache."""
    global _provider_instances
    _provider_instances.clear()
    logging.info("Cleared all provider instances from cache")