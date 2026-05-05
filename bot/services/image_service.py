from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger(__name__)


class ImageGenerationService:
    def __init__(self) -> None:
        self._api_key = os.getenv("LEONARDO_URL")
        self._base_url = "https://cloud.leonardo.ai/api/rest/v1"
    
    def is_configured(self) -> bool:
        return bool(self._api_key)
    
    def _upload_image(self, image_data: str, client) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        
        import io
        image_bytes = base64.b64decode(image_data)
        files = {"file": ("image.jpg", io.BytesIO(image_bytes), "image/jpeg")}
        
        response = client.post(
            f"{self._base_url}/upload-init",
            headers=headers,
            files=files
        )
        
        if response.status_code != 200:
            logger.error(f"Upload error: {response.text}")
            return None
        
        data = response.json()
        return data.get("uploadedImageId")
    
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
    
    def edit_image(self, image_data: str, prompt: str) -> dict:
        if not self._api_key:
            return {"error": "LEONARDO_URL not configured"}
        
        import httpx
        
        try:
            with httpx.Client(timeout=180) as client:
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                }
                
                init_resp = client.post(
                    f"{self._base_url}/init-image",
                    headers=headers,
                    json={"extension": "jpg"}
                )
                
                if init_resp.status_code != 200:
                    logger.error(f"Init error: {init_resp.status_code} - {init_resp.text}")
                    return {"error": f"Init failed: {init_resp.status_code}"}
                
                init_data = init_resp.json()
                upload_info = init_data.get("uploadInitImage", {})
                image_id = upload_info.get("id")
                
                if not image_id:
                    return {"error": "No image ID returned", "data": str(init_data)[:200]}
                
                upload_url = upload_info.get("url")
                fields_str = upload_info.get("fields", "{}")
                
                import json
                fields = json.loads(fields_str)
                
                files = {"file": ("image.jpg", base64.b64decode(image_data), "image/jpeg")}
                
                upload_resp = client.post(
                    upload_url,
                    data=fields,
                    files=files
                )
                
                if upload_resp.status_code not in (200, 204):
                    logger.error(f"S3 upload error: {upload_resp.status_code} - {upload_resp.text}")
                    return {"error": f"S3 upload failed: {upload_resp.status_code}"}
                
                gen_headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "prompt": prompt,
                    "init_image_id": image_id,
                    "width": 512,
                    "height": 512,
                    "num_images": 1,
                    "guidance_scale": 7.5,
                    "num_inference_steps": 30
                }
                
                response = client.post(
                    f"{self._base_url}/generations",
                    headers=gen_headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Leonardo edit error: {response.status_code} - {response.text}")
                    return {"error": f"API error: {response.status_code}", "detail": response.text[:200]}
                
                data = response.json()
                logger.error(f"Generation response: {data}")
                generation_id = data.get("sdks_job_id")
                
                if not generation_id:
                    generation_id = data.get("_generationJob", {}).get("generationId")
                
                if not generation_id:
                    generation_id = data.get("generationId")
                
                if not generation_id:
                    return {"error": "No generation ID returned", "data": str(data)[:300]}
                
                for _ in range(60):
                    status_resp = client.get(
                        f"{self._base_url}/generations/{generation_id}",
                        headers=gen_headers
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
            logger.error(f"Image edit error: {e}")
            return {"error": str(e)}


image_service = ImageGenerationService()