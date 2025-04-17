from typing import Optional, Dict, Any, List, AsyncGenerator
import aiohttp
import logging
from .base import BaseAIProvider
from ...config import Config

class GitHubProvider(BaseAIProvider):
    """GitHub provider for repository operations."""
    
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(api_key, config)
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
    async def create_commit(
        self,
        files: List[Dict[str, str]],
        commit_message: str,
        branch: str = "main"
    ) -> Optional[str]:
        """
        Create a commit with multiple file changes.
        
        Args:
            files: List of files to commit, each with 'path' and 'content'
            commit_message: Commit message
            branch: Branch to commit to (default: main)
            
        Returns:
            Commit SHA if successful, None otherwise
        """
        if not self.config or not self.config.github_owner or not self.config.github_repo:
            logging.error("GitHub configuration is missing")
            return None
            
        url = f"{self.base_url}/repos/{self.config.github_owner}/{self.config.github_repo}/git/commits"
        
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                # First get the latest commit SHA
                ref_url = f"{self.base_url}/repos/{self.config.github_owner}/{self.config.github_repo}/git/refs/heads/{branch}"
                async with session.get(ref_url) as response:
                    if response.status != 200:
                        logging.error(f"Failed to get latest commit: {await response.text()}")
                        return None
                    ref_data = await response.json()
                    parent_sha = ref_data["object"]["sha"]
                
                # Create blobs for each file
                blobs = []
                for file in files:
                    blob_url = f"{self.base_url}/repos/{self.config.github_owner}/{self.config.github_repo}/git/blobs"
                    blob_data = {
                        "content": file["content"],
                        "encoding": "utf-8"
                    }
                    async with session.post(blob_url, json=blob_data) as response:
                        if response.status != 201:
                            logging.error(f"Failed to create blob: {await response.text()}")
                            return None
                        blob = await response.json()
                        blobs.append({
                            "path": file["path"],
                            "mode": "100644",
                            "type": "blob",
                            "sha": blob["sha"]
                        })
                
                # Create a tree
                tree_url = f"{self.base_url}/repos/{self.config.github_owner}/{self.config.github_repo}/git/trees"
                tree_data = {
                    "base_tree": parent_sha,
                    "tree": blobs
                }
                async with session.post(tree_url, json=tree_data) as response:
                    if response.status != 201:
                        logging.error(f"Failed to create tree: {await response.text()}")
                        return None
                    tree = await response.json()
                
                # Create commit
                commit_data = {
                    "message": commit_message,
                    "parents": [parent_sha],
                    "tree": tree["sha"]
                }
                async with session.post(url, json=commit_data) as response:
                    if response.status != 201:
                        logging.error(f"Failed to create commit: {await response.text()}")
                        return None
                    commit = await response.json()
                
                # Update reference
                ref_data = {
                    "sha": commit["sha"],
                    "force": False
                }
                async with session.patch(ref_url, json=ref_data) as response:
                    if response.status != 200:
                        logging.error(f"Failed to update reference: {await response.text()}")
                        return None
                    
                return commit["sha"]
                
        except Exception as e:
            logging.error(f"Error creating commit: {e}")
            return None
            
    async def chat_completion_stream(
        self,
        message: str,
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        """Not implemented for GitHub provider as it's for repository operations only."""
        raise NotImplementedError("GitHub provider does not support chat completion")