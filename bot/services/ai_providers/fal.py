from typing import Optional, Dict, Any, List, AsyncGenerator
import aiohttp
import logging
from .base import BaseAIProvider
from ...config import Config

class FalProvider(BaseAIProvider):
    """Fal.ai provider for image generation."""
    
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(api_key, config)
        self.base_url = "https://fal.run/fal-ai/flux"  # Changed to flux model
        
    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        style_preset: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate an image using fal.ai's flux model.
        Returns the URL of the generated image or None if generation failed.
        """
        
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Base data dictionary with required fields
        data = {
            "prompt": prompt,
            "image_size": {
                "width": width,
                "height": height
            },
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "scheduler": "dpmpp_2m",  # Best scheduler for Flux
            "enable_safety_checks": True  # Enable safety filters
        }
        
        # Add optional fields only if they are provided
        if negative_prompt:
            data["negative_prompt"] = negative_prompt
        if seed is not None:
            data["seed"] = seed
        if style_preset:
            data["style_preset"] = style_preset
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=30  # Reduced timeout since Flux is faster
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"Fal.ai API error: {error_text}")
                        return None
                    
                    # Parse the JSON response
                    response_data = await response.json()
                    
                    # The API returns a JSON with an 'images' array containing image URLs
                    if 'images' in response_data and response_data['images']:
                        # Return the URL of the first generated image
                        return response_data['images'][0]['url']
                    else:
                        logging.error(f"Unexpected Fal.ai response format: {response_data}")
                        return None
                    
        except aiohttp.ClientError as e:
            logging.error(f"Network error with Fal.ai API: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in Fal.ai provider: {e}")
            return None
            
    async def chat_completion_stream(
        self,
        message: str,
        model_config: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        image: Optional[bytes] = None
    ) -> AsyncGenerator[str, None]:
        """Not implemented for FalProvider as it's only for image generation."""
        yield "❌ This provider only supports image generation. Please use the '🎨 Generate Image' button."