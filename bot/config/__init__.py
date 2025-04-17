from typing import Dict, List, Union
from .settings import Config
from .prompts import get_system_prompt, DEFAULT_SYSTEM_PROMPT
import os
from dotenv import load_dotenv

__all__ = [
    'Config',
    'get_system_prompt',
    'DEFAULT_SYSTEM_PROMPT'
]

class Config:
    def __init__(self) -> None:
        # Load environment variables
        load_dotenv()
        
        # Bot configuration
        self.bot_token: str = os.getenv("BOT_TOKEN", "")
        self.admin_id: str = os.getenv("ADMIN_ID", "")
        self.allowed_user_ids: List[str] = os.getenv("ALLOWED_USER_IDS", "").split(",")
        
        # API Keys
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.fal_api_key: str = os.getenv("FAL_API_KEY", "")
        self.github_token: str = os.getenv("GITHUB_TOKEN", "")
        self.github_owner: str = os.getenv("GITHUB_OWNER", "")
        self.github_repo: str = os.getenv("GITHUB_REPO", "")
        
        # Polling settings
        self.polling_settings: Dict[str, Union[int, float, Dict[str, float]]] = {
            "timeout": int(os.getenv("POLLING_TIMEOUT", "10")),
            "poll_interval": float(os.getenv("POLLING_INTERVAL", "0.5")),
            "backoff": {
                "max_delay": float(os.getenv("POLLING_MAX_DELAY", "5.0")),
                "start_delay": float(os.getenv("POLLING_START_DELAY", "1.0")),
                "factor": float(os.getenv("POLLING_BACKOFF_FACTOR", "1.5")),
                "jitter": float(os.getenv("POLLING_JITTER", "0.1"))
            }
        }
        
        # Validate required configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate required configuration variables."""
        required_vars = {
            "BOT_TOKEN": self.bot_token,
            "ADMIN_ID": self.admin_id,
            "OPENROUTER_API_KEY": self.openrouter_api_key,
            "FAL_API_KEY": self.fal_api_key,
            "GITHUB_TOKEN": self.github_token,
            "GITHUB_OWNER": self.github_owner,
            "GITHUB_REPO": self.github_repo
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
    @classmethod
    def from_env(cls) -> 'Config':
        """Create a Config instance from environment variables."""
        return cls()