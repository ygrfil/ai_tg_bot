from typing import Dict, Optional, Type
from .base import BaseAIProvider
from .openrouter import OpenRouterProvider
from .fal import FalProvider
from ...config import Config
from .providers import PROVIDER_MODELS

__all__ = ['get_provider']

# Cache providers to avoid recreating them
_provider_cache: Dict[str, BaseAIProvider] = {}

def get_provider(provider_name: str, config: Config) -> BaseAIProvider:
    """
    Get an AI provider instance based on the provider name.
    Uses caching to avoid recreating providers.
    
    Args:
        provider_name: Name of the provider to get
        config: Config instance containing API keys and settings
        
    Returns:
        An instance of BaseAIProvider
        
    Raises:
        ValueError: If provider is not found
    """
    # Return cached provider if available
    if provider_name in _provider_cache:
        return _provider_cache[provider_name]
    
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
    
    # Cache the provider for future use
    _provider_cache[provider_name] = provider
    
    return provider