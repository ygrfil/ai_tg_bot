from typing import Dict
from .base import BaseAIProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider
from .groq import GroqProvider
from .perplexity import PerplexityProvider
from .deepseek import DeepSeekProvider
from ...config import Config

def get_provider(provider_name: str, config: Config) -> BaseAIProvider:
    """Get AI provider instance by name."""
    providers = {
        'openai': lambda: OpenAIProvider(config.openai_api_key, config=config),
        'claude': lambda: ClaudeProvider(config.anthropic_api_key, config=config),
        'groq': lambda: GroqProvider(config.groq_api_key, config=config),
        'perplexity': lambda: PerplexityProvider(config.perplexity_api_key, config=config),
        'deepseek': lambda: DeepSeekProvider(config.DEEPSEEK_API, config=config)
    }
    
    provider_factory = providers.get(provider_name)
    if not provider_factory:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    return provider_factory()
