from environs import Env
from typing import List

class Config:
    def __init__(self,
                 bot_token: str,
                 allowed_user_ids: List[str],
                 admin_id: str,
                 openrouter_api_key: str,
                 max_tokens: int = 1024):
        self.bot_token = bot_token
        self.allowed_user_ids = allowed_user_ids
        self.admin_id = admin_id
        self.OPENROUTER_API = openrouter_api_key
        self.max_tokens = max_tokens

    @classmethod
    def from_env(cls):
        env = Env()
        env.read_env()
        
        allowed_ids = [id.strip() for id in env.str("ALLOWED_USER_IDS").split(',')]
        
        return cls(
            bot_token=env.str("BOT_TOKEN"),
            allowed_user_ids=allowed_ids,
            admin_id=env.str("ADMIN_ID"),
            openrouter_api_key=env.str("OPENROUTER_API"),
            max_tokens=env.int("MAX_TOKENS", 4096)
        )