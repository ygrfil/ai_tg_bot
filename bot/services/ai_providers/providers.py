PROVIDER_MODELS = {
    "sonnet": {
        "name": "anthropic/claude-sonnet-4.5",
        "vision": True
    },
    "openai": {
        "name": "openai/gpt-5-chat", 
        "vision": True
    },
    "online": {
        "name": "x-ai/grok-4-fast",
        "vision": True,
        "online": True
    },
    "grok": {
        "name": "x-ai/grok-4-fast:free",
        "vision": True
    },
    "fal": {
        "name": "fal-ai/flux",
        "vision": False,
        "image_generation": True
    }
}