import logging
from typing import Optional, Dict, Any
import httpx

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

    async def send_message(self, chat_id: int, text: str, **kwargs) -> Dict[str, Any]:
        """Send a text message to a chat. Ignores extra kwargs (reply_markup, parse_mode, etc.) for compatibility."""
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        return await self._request("POST", "/messages/sendText", json=payload)

    async def send_photo(
        self, chat_id: int, photo, caption: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Send a photo to a chat.

        Accepts a file path (str), an FSInputFile, or any object with a 'path' attribute.
        Extra kwargs are ignored for compatibility.
        """
        # Try to extract a file path from various input types
        if isinstance(photo, str):
            path = photo
        elif hasattr(photo, "path"):
            path = photo.path
        else:
            logger.warning(f"send_photo: unsupported photo type {type(photo)}")
            return {"ok": False, "error": "unsupported photo type"}

        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        with open(path, "rb") as f:
            files = {"photo": f}
            return await self._request(
                "POST", "/messages/sendPhoto", data=data, files=files
            )

    async def download(
        self, file_obj, destination: Optional[str] = None
    ) -> bytes | None:
        """Download a file. Placeholder for Max compatibility — always returns empty bytes."""
        logger.warning(
            f"download called but Max does not support file download: {file_obj}"
        )
        return b""

    async def get_file(self, file_id: str) -> bytes:
        """Download a file by its file_id."""
        resp = await self._request("GET", f"/files/{file_id}")
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
