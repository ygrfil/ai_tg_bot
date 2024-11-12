from environs import Env
from typing import List

class Config:
    def __init__(self, 
                 bot_token: str,
                 allowed_user_ids: List[str],
                 admin_id: str,
                 openai_api_key: str,
                 groq_api_key: str,
                 anthropic_api_key: str,
                 perplexity_api_key: str):
        self.bot_token = bot_token
        self.allowed_user_ids = allowed_user_ids
        self.admin_id = admin_id
        self.openai_api_key = openai_api_key
        self.groq_api_key = groq_api_key
        self.anthropic_api_key = anthropic_api_key
        self.perplexity_api_key = perplexity_api_key

    @classmethod
    def from_env(cls):
        env = Env()
        env.read_env()
        
        allowed_ids = [id.strip() for id in env.str("ALLOWED_USER_IDS").split(',')]
        
        return cls(
            bot_token=env.str("BOT_TOKEN"),
            allowed_user_ids=allowed_ids,
            admin_id=env.str("ADMIN_ID"),
            openai_api_key=env.str("OPENAI_API_KEY"),
            groq_api_key=env.str("GROQ_API_KEY"),
            anthropic_api_key=env.str("ANTHROPIC_API_KEY"),
            perplexity_api_key=env.str("PERPLEXITY_API_KEY")
        ) 