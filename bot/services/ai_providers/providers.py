PROVIDER_MODELS = {
    "sonnet": {
        "name": "anthropic/claude-sonnet-4",
        "vision": True
    },
    "openai": {
        "name": "openai/o4-mini",
        "vision": True
    },
    "online": {
        "name": "perplexity/sonar:online",
        "vision": True,
        "online": True
    },
    "gemini": {
        "name": "google/gemini-2.5-pro-preview",
        "vision": True
    },
    "fal": {
        "name": "fal-ai/flux",
        "vision": False,
        "image_generation": True
    }
}