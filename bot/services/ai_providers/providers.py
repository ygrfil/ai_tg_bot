from typing import TypedDict, Literal

class ModelConfig(TypedDict):
    name: str
    vision: bool
    max_context_tokens: int
    max_output_tokens: int
    online: bool | None
    image_generation: bool | None

PROVIDER_MODELS: dict[Literal["sonnet", "openai", "online", "gemini", "fal"], ModelConfig] = {
    "sonnet": {
        "name": "anthropic/claude-3.7-sonnet",
        "vision": True,
        "max_context_tokens": 200000,
        "max_output_tokens": 4096,
        "online": None,
        "image_generation": None
    },
    "openai": {
        "name": "openai/o4-mini",
        "vision": True,
        "max_context_tokens": 128000,
        "max_output_tokens": 2048,
        "online": None,
        "image_generation": None
    },
    "online": {
        "name": "perplexity/sonar:online",
        "vision": True,
        "online": True,
        "max_context_tokens": 16000,
        "max_output_tokens": 1024,
        "image_generation": None
    },
    "gemini": {
        "name": "google/gemini-2.5-pro-preview-03-25",
        "vision": True,
        "max_context_tokens": 32000,
        "max_output_tokens": 2048,
        "online": None,
        "image_generation": None
    },
    "fal": {
        "name": "fal-ai/flux",
        "vision": False,
        "image_generation": True,
        "max_context_tokens": 4096,
        "max_output_tokens": 512,
        "online": None
    }
}