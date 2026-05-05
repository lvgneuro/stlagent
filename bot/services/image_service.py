from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class ImageGenerationService:
    def __init__(self) -> None:
        self._api_key = os.getenv("LEONARDO_URL")
        self._base_url = "https://cloud.leonardo.ai/api/rest/v1"
    
    def is_configured(self) -> bool:
        return bool(self._api_key)
    
    def generate(self, prompt: str, width: int = 512, height: int = 512) -> dict:
        if not self._api_key:
            return {"error": "LEONARDO_URL not configured"}
        
        import httpx
        
        try:
            with httpx.Client(timeout=120) as client:
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_images": 1,
                    "guidance_scale": 7.5,
                    "num_inference_steps": 30
                }
                
                response = client.post(
                    f"{self._base_url}/generations",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Leonardo error: {response.text}")
                    return {"error": f"API error: {response.status_code}"}
                
                data = response.json()
                
                generation_id = data.get("_generationJob", {}).get("generationId")
                if not generation_id:
                    generation_id = data.get("sdks_job_id")
                
                if not generation_id:
                    return {"error": "No generation ID returned"}
                
                for _ in range(60):
                    status_resp = client.get(
                        f"{self._base_url}/generations/{generation_id}",
                        headers=headers
                    )
                    status_data = status_resp.json()
                    status = status_data.get("generationJob", {}).get("status", "UNKNOWN")
                    
                    if status == "COMPLETE":
                        images = status_data.get("generationJob", {}).get("generated_images", [])
                        if images:
                            return {"url": images[0].get("url", "")}
                    elif status == "FAILED":
                        return {"error": "Generation failed"}
                    
                    import time
                    time.sleep(2)
                
                return {"error": "Timeout waiting for image"}
                
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return {"error": str(e)}


image_service = ImageGenerationService()