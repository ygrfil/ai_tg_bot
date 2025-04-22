#!/usr/bin/env python
"""Test script to verify history conversion between formats."""

import asyncio
import logging
import json
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sample history data in storage format (with is_bot)
storage_format = [
    {"content": "Hello, how can I help you?", "is_bot": True, "timestamp": "2025-04-22 04:00:01"},
    {"content": "What's 22+22?", "is_bot": False, "timestamp": "2025-04-22 04:01:58"},
    {"content": "44", "is_bot": True, "timestamp": "2025-04-22 04:02:02"}
]

def convert_to_role_format(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert history from storage format (is_bot) to role format."""
    converted_history = []
    
    for msg in history:
        if not isinstance(msg, dict):
            logger.warning(f"Skipping non-dict history item: {msg}")
            continue
            
        # Handle storage format with is_bot
        if 'is_bot' in msg and 'content' in msg:
            is_bot = msg['is_bot']
            role = "assistant" if is_bot else "user"
            content = msg['content']
            
            # Add to converted history
            converted_history.append({
                "role": role,
                "content": content
            })
            logger.debug(f"Converted history message: {role} - {content[:20]}...")
        # Handle already formatted messages
        elif 'role' in msg and 'content' in msg:
            converted_history.append(msg)
        else:
            logger.warning(f"Skipping invalid message format: {msg}")
            
    return converted_history

def format_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format conversation history for the model."""
    formatted_history = []
    
    for msg in history:
        if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
            logger.warning(f"Skipping invalid message in history: {msg}")
            continue
            
        role = msg['role']
        content = msg['content']
        
        # Validate role
        if role not in ['system', 'user', 'assistant']:
            logger.warning(f"Invalid role in message: {role}")
            continue
        
        # Handle different content types
        if isinstance(content, str):
            # Handle simple text messages
            if content.strip():  # Only add non-empty messages
                formatted_history.append({
                    "role": role,
                    "content": content
                })
        else:
            logger.warning(f"Skipping message with invalid content type: {type(content)}")
            
    return formatted_history

async def main():
    # Print original format
    logger.info("Original storage format:")
    for msg in storage_format:
        logger.info(f"  {'Bot' if msg['is_bot'] else 'User'}: {msg['content']}")
    
    # Convert to role format
    converted = convert_to_role_format(storage_format)
    logger.info("\nConverted to role format:")
    for msg in converted:
        logger.info(f"  {msg['role'].capitalize()}: {msg['content']}")
    
    # Apply formatting
    formatted = format_history(converted)
    logger.info("\nAfter formatting:")
    for msg in formatted:
        logger.info(f"  {msg['role'].capitalize()}: {msg['content']}")
    
    # Create sample messages list for API
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]
    messages.extend(formatted)
    
    logger.info("\nFinal messages for API:")
    for msg in messages:
        logger.info(f"  {msg['role'].capitalize()}: {msg['content']}")

if __name__ == "__main__":
    asyncio.run(main()) 