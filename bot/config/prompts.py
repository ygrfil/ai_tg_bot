"""Module containing the system prompt configuration."""

# Default system prompt used across all models
DEFAULT_SYSTEM_PROMPT = """You are an AI assistant optimized for Telegram conversations. Enhance your responses with:

💡 Essential Formatting:
• <b>bold</b> for key points
• <i>italic</i> for emphasis
• <code>monospace</code> for technical content
• <pre>blocks</pre> for code
• <a href="URL">links</a> for references

📝 Text Structure:
• Use paragraphs to separate different ideas
• Add blank lines between sections
• Keep paragraphs short (2-3 sentences)
• Use lists for multiple points



Keep responses concise, informative, and well-structured. Use formatting and emojis purposefully to enhance readability."""

# List of providers that need system_prompt as a parameter instead of a message
SYSTEM_PROMPT_AS_PARAMETER = [
    "openrouter",  # For OpenRouter API
]

# List of providers that don't need system prompts at all (e.g., image generation)
NO_SYSTEM_PROMPT_PROVIDERS = [
    "fal",  # Image generation provider
]

def get_system_prompt(model_name: str) -> str:
    """Get the system prompt regardless of model."""
    return DEFAULT_SYSTEM_PROMPT

def uses_system_prompt_parameter(provider_name: str) -> bool:
    """Check if the provider uses system_prompt as a parameter instead of a message."""
    return provider_name.lower() in SYSTEM_PROMPT_AS_PARAMETER

def needs_system_prompt(provider_name: str) -> bool:
    """Check if the provider needs a system prompt at all."""
    return provider_name.lower() not in NO_SYSTEM_PROMPT_PROVIDERS