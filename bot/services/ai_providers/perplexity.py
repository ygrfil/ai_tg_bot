from .openai import OpenAIProvider

class PerplexityProvider(OpenAIProvider):
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )