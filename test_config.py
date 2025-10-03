#!/usr/bin/env python3
"""
Test script to check bot configuration and API keys.
Run this script to diagnose configuration issues.
"""

import asyncio
import logging
import os
import time
from bot.config import Config
from bot.services.ai_providers import get_provider
from bot.services.ai_providers.providers import PROVIDER_MODELS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_configuration():
    """Test the bot configuration and API keys."""
    print("🔍 Testing Bot Configuration...")
    
    try:
        # Load configuration
        config = Config.from_env()
        print("✅ Configuration loaded successfully")
        
        # Check environment variables
        print(f"\n📋 Configuration Details:")
        print(f"Bot Token: {'✅ Set' if config.bot_token else '❌ Missing'}")
        print(f"Admin ID: {config.admin_id}")
        print(f"Allowed Users: {len(config.allowed_user_ids)} users")
        print(f"OpenRouter API Key: {'✅ Set' if config.openrouter_api_key else '❌ Missing'}")
        print(f"Fal API Key: {'✅ Set' if config.fal_api_key else '❌ Missing'}")
        
        # Test AI providers
        print(f"\n🤖 Testing AI Providers:")
        for provider_name in ["openai", "sonnet", "grok"]:
            if provider_name in PROVIDER_MODELS:
                try:
                    provider = await get_provider(provider_name, config)
                    print(f"✅ {provider_name}: Provider initialized")
                    
                    # Test a simple request
                    try:
                        model_config = PROVIDER_MODELS[provider_name]
                        start_time = time.time()
                        response_stream = provider.chat_completion_stream(
                            message="Hello, this is a test.",
                            model_config=model_config,
                            history=None
                        )
                        
                        # Get first chunk to test
                        first_chunk = None
                        chunk_count = 0
                        async for chunk in response_stream:
                            chunk_count += 1
                            first_chunk = chunk
                            if chunk_count >= 5:  # Get a few chunks to test
                                break
                        
                        end_time = time.time()
                        response_time = end_time - start_time
                        
                        if first_chunk:
                            print(f"✅ {provider_name}: API request successful ({response_time:.2f}s, {chunk_count} chunks)")
                        else:
                            print(f"⚠️ {provider_name}: No response received ({response_time:.2f}s)")
                            
                    except Exception as e:
                        print(f"❌ {provider_name}: API request failed - {str(e)}")
                        
                except Exception as e:
                    print(f"❌ {provider_name}: Provider initialization failed - {str(e)}")
            else:
                print(f"⚠️ {provider_name}: Not configured")
        
        print(f"\n✅ Configuration test completed!")
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        logging.error(f"Configuration test error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_configuration())
