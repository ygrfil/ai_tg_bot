from typing import Dict
from .base import BaseAIProvider
from .openrouter import OpenRouterProvider
from ...config import Config
from .providers import PROVIDER_MODELS

def get_provider(provider_name: str, config: Config) -> BaseAIProvider:
    """Get AI provider instance by name.
    
    Args:
        provider_name: The provider name (e.g., 'sonnet', 'gpt4', etc.)
        config: The configuration object containing API keys
        
    Returns:
        An instance of OpenRouterProvider configured for the requested model
        
    Raises:
        ValueError: If provider_name is not found in PROVIDER_MODELS
    """
    if provider_name.lower() not in PROVIDER_MODELS:
        valid_providers = ", ".join(PROVIDER_MODELS.keys())
        raise ValueError(f"Unknown provider: {provider_name}. Valid providers are: {valid_providers}")
    
    # Get model config and create provider instance
    model_config = PROVIDER_MODELS[provider_name.lower()]
    provider = OpenRouterProvider(config.OPENROUTER_API, config=config)
    provider.model_name = model_config['name']  # Set the specific OpenRouter model name
    provider.vision = model_config['vision']  # Set vision capability
    
    return provider
