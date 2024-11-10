from typing import Dict, List, Optional

# Store conversation history in memory
_conversation_history: Dict[int, List[Dict]] = {}

def get_conversation_history(user_id: int) -> List[Dict]:
    """Get conversation history for a user"""
    if user_id not in _conversation_history:
        _conversation_history[user_id] = []
    return _conversation_history[user_id]

def set_conversation_history(user_id: int, messages: List[Dict]) -> None:
    """Set conversation history for a user"""
    _conversation_history[user_id] = messages

def clear_conversation_history(user_id: int) -> None:
    """Clear conversation history for a user"""
    _conversation_history[user_id] = [] 