PROVIDER_MODELS = {
    "sonnet": {
        "name": "anthropic/claude-3.7-sonnet",
        "vision": True,
        "max_context_tokens": 200000,
        "max_output_tokens": 4096
    },
    "openai": {
        "name": "openai/o4-mini",
        "vision": True,
        "max_context_tokens": 128000,
        "max_output_tokens": 2048
    },
    "online": {
        "name": "perplexity/sonar:online",
        "vision": True,
        "online": True,
        "max_context_tokens": 16000,
        "max_output_tokens": 1024
    },
    "gemini": {
        "name": "google/gemini-2.5-pro-preview-03-25",
        "vision": True,
        "max_context_tokens": 32000,
        "max_output_tokens": 2048
    },
    "fal": {
        "name": "fal-ai/flux",
        "vision": False,
        "image_generation": True,
        "max_context_tokens": 4096,
        "max_output_tokens": 512
    }
}