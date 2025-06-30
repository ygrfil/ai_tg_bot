PROVIDER_MODELS = {
    "sonnet": {
        "name": "anthropic/claude-3.5-sonnet",
        "vision": True
    },
    "openai": {
        "name": "openai/gpt-4o-mini", 
        "vision": True
    },
    "online": {
        "name": "openai/gpt-4o",
        "vision": True,
        "online": False
    },
    "gemini": {
        "name": "google/gemini-flash-1.5",
        "vision": True
    },
    "fal": {
        "name": "fal-ai/flux",
        "vision": False,
        "image_generation": True
    }
}