# Telegram Rate Limits Optimization Plan

## Current Issues
1. Hitting Telegram's flood control on GetUpdates method
2. Experiencing Bad Gateway errors
3. Default polling configuration leading to too frequent requests

## Proposed Solutions

### 1. Configure Polling Parameters
Add proper polling configuration when starting the bot:

```python
# Polling configuration
POLLING_SETTINGS = {
    "timeout": 10,  # Long polling timeout in seconds
    "poll_interval": 0.5,  # Minimum interval between requests
    "backoff": {
        "max_delay": 5.0,  # Maximum delay between retries
        "start_delay": 1.0,  # Initial retry delay
        "factor": 1.5,  # Multiplier for each retry
        "jitter": 0.1,  # Random jitter to avoid synchronization
    }
}
```

### 2. Implement Exponential Backoff
Create a dedicated polling middleware to handle rate limits and retries:

```python
class PollingMiddleware:
    def __init__(self, settings: dict):
        self.settings = settings
        self.current_delay = settings["backoff"]["start_delay"]
        self.failed_attempts = 0

    async def __call__(self, handler, event, data):
        try:
            result = await handler(event, data)
            # Reset backoff on success
            self.current_delay = self.settings["backoff"]["start_delay"]
            self.failed_attempts = 0
            return result
        except Exception as e:
            if "Flood control" in str(e):
                await self.handle_rate_limit()
            raise

    async def handle_rate_limit(self):
        self.failed_attempts += 1
        jitter = random.uniform(
            -self.settings["backoff"]["jitter"],
            self.settings["backoff"]["jitter"]
        )
        
        # Calculate next delay with jitter
        next_delay = min(
            self.current_delay * self.settings["backoff"]["factor"],
            self.settings["backoff"]["max_delay"]
        )
        self.current_delay = next_delay + jitter
        
        await asyncio.sleep(self.current_delay)
```

### 3. Update Main.py Implementation

```python
async def main():
    # ... existing initialization code ...

    # Initialize polling middleware
    polling_middleware = PollingMiddleware(POLLING_SETTINGS)
    dp.update.outer_middleware(polling_middleware)

    # Start polling with configured settings
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        polling_timeout=POLLING_SETTINGS["timeout"],
        polling_interval=POLLING_SETTINGS["poll_interval"]
    )
```

## Expected Improvements

1. **Reduced Rate Limit Hits**: The configured polling interval ensures we don't overwhelm Telegram's servers
2. **Better Error Recovery**: Exponential backoff helps recover from rate limits gradually
3. **More Stable Operation**: Jitter helps prevent request synchronization issues
4. **Efficient Resource Usage**: Longer polling timeout reduces unnecessary requests

## Implementation Steps

1. Add POLLING_SETTINGS configuration to bot/config/settings.py
2. Create new middleware in bot/utils/polling.py
3. Update main.py to use the new polling configuration
4. Add logging to track rate limit occurrences and recovery

## Monitoring

Add enhanced logging to track:
- Rate limit occurrences
- Backoff delays
- Recovery times
- Request frequencies

This will help tune the settings based on real usage patterns.