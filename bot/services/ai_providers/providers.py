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
        "name": "google/gemini-2.5-flash",
        "vision": True,
        "online": False
    },
    "gemini": {
        "name": "google/gemini-2.5-flash",
        "vision": True
    },
    "fal": {
        "name": "fal-ai/flux",
        "vision": False,
        "image_generation": True
    }
}