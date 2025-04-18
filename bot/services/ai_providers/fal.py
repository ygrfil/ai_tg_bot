from typing import Optional, Dict, Any, List, AsyncGenerator
import aiohttp
import logging
import asyncio
from .base import BaseAIProvider
from ...config import Config

class FalProvider(BaseAIProvider):
    """Fal.ai provider for image generation."""
    
    def __init__(self, api_key: str, config: Config = None):
        super().__init__(api_key, config)
        # Using FLUX.1 [dev] model as it offers the best balance of:
        # - High image quality with excellent detail, text rendering, and realism
        # - Reasonable generation speed (3-4s per image)
        # - Cost-effective pricing ($25 per 1000 images)
        self.base_url = "https://fal.run/fal-ai/flux/dev"
        
    async def _poll_queue_status(self, request_id: str, headers: Dict[str, str], max_retries: int = 30) -> Optional[Dict]:
        """Poll the queue status until the request is completed or fails."""
        retries = 0
        
        while retries < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    # Use the subscription endpoint for status checking
                    async with session.post(
                        self.base_url + "/subscribe",
                        headers=headers,
                        json={"request_id": request_id}
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logging.error(f"Error checking queue status: {error_text}")
                            return None
                            
                        result = await response.json()
                        
                        # Check if we have the final result
                        if "error" in result:
                            logging.error(f"Image generation failed: {result['error']}")
                            return None
                        elif "images" in result:
                            return result
                        else:
                            # Still processing, wait before next check
                            await asyncio.sleep(1)
                            retries += 1
                            continue
                            
            except Exception as e:
                logging.error(f"Error polling queue status: {e}")
                return None
                
        logging.error("Max retries reached while waiting for image generation")
        return None
        
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
        
        # Prepare request data according to fal.ai docs
        data = {
            "prompt": prompt,  # Prompt should be at the root level
            "negative_prompt": negative_prompt if negative_prompt else "",
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "width": width,
            "height": height,
            "scheduler": "dpmpp_2m",  # Best scheduler for Flux
            "enable_safety_checker": True  # Enable safety filters
        }
        
        # Add optional fields only if they are provided
        if seed is not None:
            data["seed"] = seed
        if style_preset:
            data["style_preset"] = style_preset
        
        try:
            async with aiohttp.ClientSession() as session:
                # Submit the generation request
                async with session.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"Fal.ai API error: {error_text}")
                        return None
                    
                    result = await response.json()
                    
                    # Check if we have images in the response
                    if "images" in result and result["images"]:
                        return result["images"][0]["url"]
                    else:
                        logging.error(f"No images in result: {result}")
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