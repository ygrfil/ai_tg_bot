#!/usr/bin/env python3
"""
Test script to check bot response time with a real message.
"""

import asyncio
import logging
import time
from bot.config import Config
from bot.services.ai_providers import get_provider
from bot.services.ai_providers.providers import PROVIDER_MODELS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_bot_response():
    """Test the bot's response time with a real message."""
    print("🤖 Testing Bot Response Time...")
    
    try:
        # Load configuration
        config = Config.from_env()
        print("✅ Configuration loaded successfully")
        
        # Test with different providers
        test_message = "Write a short paragraph about artificial intelligence in 2-3 sentences."
        
        for provider_name in ["openai", "sonnet", "grok"]:
            if provider_name in PROVIDER_MODELS:
                print(f"\n🧪 Testing {provider_name}...")
                
                try:
                    provider = await get_provider(provider_name, config)
                    model_config = PROVIDER_MODELS[provider_name]
                    
                    start_time = time.time()
                    
                    # Simulate the bot's streaming process
                    response_text = ""
                    chunk_count = 0
                    async for chunk in provider.chat_completion_stream(
                        message=test_message,
                        model_config=model_config,
                        history=None
                    ):
                        if chunk and chunk.strip():
                            response_text += chunk
                            chunk_count += 1
                            
                            # Simulate message updates every 100 chars
                            if len(response_text) % 100 == 0:
                                print(f"  📝 Progress: {len(response_text)} chars, {chunk_count} chunks")
                    
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    print(f"✅ {provider_name} completed in {total_time:.2f}s")
                    print(f"   Response length: {len(response_text)} chars")
                    print(f"   Chunks received: {chunk_count}")
                    print(f"   Response: {response_text[:150]}...")
                    
                except Exception as e:
                    print(f"❌ {provider_name} failed: {e}")
        
        print(f"\n✅ Bot response test completed!")
        
    except Exception as e:
        print(f"❌ Bot response test failed: {e}")
        logging.error(f"Bot response test error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_bot_response())
