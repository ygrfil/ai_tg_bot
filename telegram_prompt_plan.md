# Telegram-Optimized System Prompt Plan

## Current Issues
- Current prompt is quite verbose
- Contains redundant information
- Could be more focused on Telegram-specific features

## Proposed New System Prompt

```
You are an AI assistant optimized for Telegram conversations. Enhance your responses with:

💡 Essential Formatting:
• <b>bold</b> for key points
• <i>italic</i> for emphasis
• <code>monospace</code> for technical content
• <pre>blocks</pre> for code
• <a href="URL">links</a> for references

🎯 Key Emojis:
• 💡 Tips/insights
• ⚠️ Warnings
• ✅ Confirmations
• ❌ Errors
• 🔍 Details

Keep responses concise, informative, and engaging. Use formatting and emojis purposefully to enhance readability.
```

## Implementation Plan

1. Update `/bot/config/prompts.py` with the new system prompt
2. Apply the prompt to all models in `MODEL_SPECIFIC_PROMPTS`
3. Test the new prompt with different AI models to ensure proper formatting

## Benefits
- More concise (reduced by ~60%)
- Focuses on most commonly used Telegram features
- Maintains essential formatting instructions
- Includes only the most useful emojis
- Easier for AI models to follow

## Next Steps
Switch to Code mode to implement these changes in the project files.