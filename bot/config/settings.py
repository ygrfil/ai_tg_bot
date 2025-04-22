from environs import Env
from typing import List, Dict, Any
import json
import os
from pathlib import Path

class Config:
    def __init__(self,
                 bot_token: str,
                 allowed_user_ids: List[str],
                 admin_id: str,
                 openrouter_api_key: str,
                 fal_api_key: str,
                 max_tokens: int = 1024,
                 polling_settings: Dict[str, Any] = None):
        self.bot_token = bot_token
        self.allowed_user_ids = allowed_user_ids
        self.admin_id = admin_id
        self.openrouter_api_key = openrouter_api_key
        self.fal_api_key = fal_api_key
        self.max_tokens = max_tokens
        
        # Default polling settings
        self.polling_settings = polling_settings or {
            "timeout": 10,
            "poll_interval": 0.5,
            "backoff": {
                "max_delay": 5.0,
                "start_delay": 1.0,
                "factor": 1.5,
                "jitter": 0.1,
            }
        }

        # Dynamic state storage
        self._state: Dict[str, Any] = {}
        self._state_file = Path("bot_state.json")
        self._load_state()

    def __getattr__(self, name: str) -> Any:
        """Handle dynamic attribute access."""
        return self._state.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Handle dynamic attribute setting."""
        if name in ['bot_token', 'allowed_user_ids', 'admin_id', 'openrouter_api_key', 
                   'fal_api_key', 'max_tokens', 'polling_settings', '_state', '_state_file']:
            super().__setattr__(name, value)
        else:
            self._state[name] = value
            self._save_state()

    def _load_state(self) -> None:
        """Load state from file."""
        try:
            if self._state_file.exists():
                with open(self._state_file, 'r') as f:
                    self._state = json.load(f)
        except Exception as e:
            print(f"Error loading state: {e}")
            self._state = {}

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            with open(self._state_file, 'w') as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")

    @classmethod
    def from_env(cls):
        env = Env()
        env.read_env()
        
        allowed_ids = [id.strip() for id in env.str("ALLOWED_USER_IDS").split(',')]
        
        # Load polling settings from environment if provided
        polling_settings = {
            "timeout": env.int("POLLING_TIMEOUT", 10),
            "poll_interval": env.float("POLLING_INTERVAL", 0.5),
            "backoff": {
                "max_delay": env.float("POLLING_MAX_DELAY", 5.0),
                "start_delay": env.float("POLLING_START_DELAY", 1.0),
                "factor": env.float("POLLING_BACKOFF_FACTOR", 1.5),
                "jitter": env.float("POLLING_JITTER", 0.1),
            }
        }
        
        return cls(
            bot_token=env.str("BOT_TOKEN"),
            allowed_user_ids=allowed_ids,
            admin_id=env.str("ADMIN_ID"),
            openrouter_api_key=env.str("OPENROUTER_API_KEY"),
            fal_api_key=env.str("FAL_API_KEY"),
            max_tokens=env.int("MAX_TOKENS", 4096),
            polling_settings=polling_settings
        )

    def clear_attribute(self, name: str) -> None:
        """Remove a dynamic attribute from state."""
        if name in self._state:
            del self._state[name]
            self._save_state()
            
    def clear_all_attributes(self) -> None:
        """Clear all dynamic attributes."""
        self._state = {}
        self._save_state()