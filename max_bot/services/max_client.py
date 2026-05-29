import logging
from typing import Optional, Dict, Any, List
import httpx
from pathlib import Path

logger = logging.getLogger(__name__)

class MaxBot:
    def __init__(self, token: str, **kwargs):
        # Ignore any extra keyword arguments (like parse_mode) for compatibility
        self.token = token
        self.base_url = "https://platform-api.max.ru"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = self.token
        url = f"{self.base_url}{endpoint}"
        response = await self.client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    async def send_message(self, chat_id: int, text: str) -> Dict[str, Any]:
        """Send a text message to a chat."""
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        return await self._request("POST", "/messages/sendText", json=payload)

    async def send_photo(self, chat_id: int, photo_path: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """Send a photo to a chat."""
        # For simplicity, we assume photo_path is a local file path and we need to upload it.
        # In a real implementation, you might need to upload the photo first to get a file_id.
        # Since Max API specifics are not detailed, we'll note that this needs adaptation.
        # This is a placeholder.
        files = {"photo": open(photo_path, "rb")}
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        # We need to know the correct endpoint for sending photos in Max API.
        # As an example, let's assume it's /messages/sendPhoto
        return await self._request("POST", "/messages/sendPhoto", data=data, files=files)

    async def get_file(self, file_id: str) -> bytes:
        """Download a file by its file_id."""
        # This is a placeholder; actual implementation depends on Max API.
        resp = await self._request("GET", f"/files/{file_id}")
        # Assuming the response contains a URL to download the file
        file_url = resp.get("url")
        if not file_url:
            raise ValueError("No file URL in response")
        download_resp = await self.client.get(file_url)
        download_resp.raise_for_status()
        return download_resp.content

    async def set_webhook(self, url: str) -> Dict[str, Any]:
        """Set the webhook URL for receiving updates."""
        payload = {"url": url}
        return await self._request("POST", "/setWebhook", json=payload)

    async def delete_webhook(self) -> Dict[str, Any]:
        """Remove the webhook integration."""
        return await self._request("POST", "/deleteWebhook")

    # Additional methods as needed (e.g., get_chat, etc.) can be added here.

    async def close(self):
        await self.client.aclose()