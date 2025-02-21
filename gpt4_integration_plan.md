# Plan: Adding ChatGPT-4-latest Model

## Current Setup
- Models are configured in `bot/services/ai_providers/providers.py`
- Implementation uses OpenRouter API (bot/services/ai_providers/openrouter.py)
- Existing models follow pattern: provider/model-name (e.g., openai/o3-mini)

## Integration Steps
1. Add new model configuration to PROVIDER_MODELS dictionary:
```python
"gpt4-latest": {
    "name": "openai/gpt-4-latest",
    "vision": True  # GPT-4 supports vision capabilities
}
```

2. No additional changes needed to openrouter.py as it's already set up to handle:
   - API communication
   - Vision capabilities
   - Streaming responses
   - Error handling

## Next Steps
1. Switch to Code mode to implement the changes
2. Test the new model with:
   - Basic text completion
   - Vision capabilities
   - Streaming responses

Would you like to proceed with this implementation plan?