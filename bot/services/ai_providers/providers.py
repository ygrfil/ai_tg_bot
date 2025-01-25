PROVIDER_MODELS = {
    "openai": {
        "name": "chatgpt-4o-latest",
        "vision": True
    },
    "groq": {
        "name": "llama-3.3-70b-versatile",
        "vision": False
    },
    "claude": {
        "name": "claude-3-5-sonnet-latest",
        "vision": True
    },
    "perplexity": {
        "name": "sonar-pro",
        "vision": False
    },
    "deepseek": {
        "name": "deepseek-chat",
        "vision": False,
        "base_url": "https://api.deepseek.com/v1",
        "env_var": "DEEPSEEK_API"
    }
}