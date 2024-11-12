import json
import os
from typing import Dict, Any, List
from ..config import Config
from datetime import datetime

class JsonStorage:
    def __init__(self, settings_path: str):
        self.settings_path = settings_path
        self.history_path = settings_path.replace('user_settings.json', 'chat_history.json')
        self._ensure_files_exist()
        self.config = Config.from_env()

    def _ensure_files_exist(self):
        """Ensure both settings and history files exist with proper permissions"""
        for file_path in [self.settings_path, self.history_path]:
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Create file if it doesn't exist
                if not os.path.exists(file_path):
                    with open(file_path, 'w') as f:
                        json.dump({}, f, indent=2)
                    print(f"Created new file: {file_path}")  # Debug print
                
                # Verify file is writable
                if not os.access(file_path, os.W_OK):
                    print(f"Warning: File not writable: {file_path}")  # Debug print
                    
            except Exception as e:
                print(f"Error ensuring file exists: {file_path} - {str(e)}")  # Debug print

    def _load_settings(self) -> Dict[str, Any]:
        try:
            with open(self.settings_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_settings(self, data: Dict[str, Any]):
        with open(self.settings_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_history(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.history_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_history(self, data: Dict[str, List[Dict[str, Any]]]):
        with open(self.history_path, 'w') as f:
            json.dump(data, f, indent=2)

    def is_user_allowed(self, user_id: int) -> bool:
        user_id_str = str(user_id)
        return (user_id_str in self.config.allowed_user_ids or 
                user_id_str == self.config.admin_id)

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        data = self._load_settings()
        return data.get(str(user_id), {})

    def update_user_settings(self, user_id: int, settings: Dict[str, Any]):
        data = self._load_settings()
        data[str(user_id)] = settings
        self._save_settings(data)

    def add_to_history(self, user_id: int, message: Dict[str, Any]):
        """Add a message to user's history"""
        data = self._load_history()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = []
        
        # Add timestamp to message
        message["timestamp"] = datetime.now().isoformat()
        
        # Add message to history
        data[user_id_str].append(message)
        
        self._save_history(data)

    def get_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user's history"""
        try:
            with open(self.history_path, 'r') as f:
                data = json.load(f)
                history = data.get(str(user_id), [])
                return history[-limit:] if limit else history
        except Exception:
            return []

    def clear_history(self, user_id: int) -> bool:
        """Clear user's history"""
        try:
            # Load current history
            with open(self.history_path, 'r') as f:
                data = json.load(f)
            
            user_id_str = str(user_id)
            
            # Reset history for user
            data[user_id_str] = []
            
            # Save empty history
            with open(self.history_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception:
            return False
