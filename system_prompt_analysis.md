# System Prompt Analysis

## Current Implementation

1. **Configuration**
   - Default system prompt is defined in `bot/config/prompts.py`
   - Used consistently across all models
   - Contains Telegram-specific formatting instructions

2. **Usage Flow**
   - BaseAIProvider imports DEFAULT_SYSTEM_PROMPT
   - OpenRouterProvider inherits and uses _get_system_prompt()
   - System prompt is properly added as first message in all conversations

## Findings

✅ **What's Working**
- System prompt is consistently applied across all models
- Contains good Telegram-specific formatting guidance
- Properly integrated into the message chain
- Implementation is clean and maintainable

⚠️ **Potential Improvements**
1. Duplicate functionality:
   - `prompts.py::get_system_prompt()`
   - `base.py::_get_system_prompt()`
   Both simply return DEFAULT_SYSTEM_PROMPT

2. Unused potential:
   - get_system_prompt() accepts a model_name parameter but doesn't use it
   - Could be useful for model-specific customizations

## Recommendations

1. **Consolidate Prompt Functions**
   - Remove _get_system_prompt() from BaseAIProvider
   - Use prompts.get_system_prompt() directly
   - This centralizes prompt management in prompts.py

2. **Enable Model-Specific Prompts**
   - Implement model-specific customizations in prompts.get_system_prompt()
   - Could be useful for models with different capabilities or requirements
   - Example: Vision models might need additional image-related instructions

3. **Future Considerations**
   - Consider adding provider-specific prompt variations if needed
   - Add validation to ensure prompts don't exceed model context limits
   - Consider adding prompt templates for different use cases

## Implementation Plan

1. Update prompts.py to support model-specific variations:
```python
def get_system_prompt(model_name: str) -> str:
    """Get the system prompt for specific model."""
    # Add model-specific customizations here if needed
    return DEFAULT_SYSTEM_PROMPT
```

2. Modify BaseAIProvider to use centralized prompt management:
```python
from bot.config.prompts import get_system_prompt

class BaseAIProvider(ABC):
    def _get_system_prompt(self, model_name: str) -> str:
        return get_system_prompt(model_name)
```

This refactoring would maintain current functionality while enabling future model-specific customizations when needed.