from typing import Dict
from .base import BaseAIProvider
from .groq import GroqProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider
from .perplexity import PerplexityProvider
from ...config import Config

_providers: Dict[str, BaseAIProvider] = {}

def init_providers():
    config = Config.from_env()
    
    global _providers
    _providers = {
        "groq": GroqProvider(config.groq_api_key),
        "openai": OpenAIProvider(config.openai_api_key),
        "claude": ClaudeProvider(config.anthropic_api_key),
        "perplexity": PerplexityProvider(config.perplexity_api_key)
    }

def get_provider(name: str) -> BaseAIProvider:
    if not _providers:
        init_providers()
    return _providers[name]
