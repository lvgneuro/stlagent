from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class MaxBot:
    def __init__(self, token: str, **kwargs):
        self.token = token
        self.id = 0
        self.username: str | None = None
        self.base_url = "https://platform-api.max.ru"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __call__(self, method) -> Any:
        """Handle aiogram TelegramMethod calls (e.g. from message.answer())."""
        method_name = type(method).__name__
        if method_name == "SendMessage":
            return await self.send_message(method.chat_id, method.text)
        if method_name == "SendPhoto":
            return await self.send_photo(method.chat_id, method.photo, caption=getattr(method, "caption", None))
        if method_name == "DeleteMessage":
            return {"ok": True}
        if method_name == "CopyMessage":
            return await self.send_message(method.chat_id, getattr(method, "caption", "") or "")
        logger.warning(f"MaxBot.__call__: unsupported method {method_name}")
        return {"ok": False, "error": f"unsupported method {method_name}"}

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = self.token
        url = f"{self.base_url}{endpoint}"
        response = await self.client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    async def send_message(self, chat_id: int, text: str, **kwargs) -> Dict[str, Any]:
        payload: dict[str, Any] = {"text": text}
        if kwargs.get("parse_mode") in ("HTML", "Markdown"):
            payload["format"] = kwargs["parse_mode"].lower()
        return await self._request("POST", "/messages", json=payload)

    async def send_photo(
        self, chat_id: int, photo, caption: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        # For MAX, send photo as a message with image attachment
        if isinstance(photo, str):
            path = photo
        elif hasattr(photo, "path"):
            path = photo.path
        else:
            logger.warning(f"send_photo: unsupported photo type {type(photo)}")
            return {"ok": False, "error": "unsupported photo type"}
        data: dict[str, Any] = {}
        if caption:
            data["caption"] = caption
        with open(path, "rb") as f:
            files = {"file": f}
            return await self._request(
                "POST", "/messages", data=data, files=files
            )

    async def download(self, file_obj, destination: Optional[str] = None) -> bytes | None:
        logger.warning(f"download called but MAX file download not supported: {file_obj}")
        return b""

    async def get_file(self, file_id: str) -> bytes:
        resp = await self._request("GET", f"/messages/{file_id}")
        # Response may contain file URL or data
        return resp.get("content", b"")

    async def set_webhook(self, url: str) -> Dict[str, Any]:
        payload = {"url": url}
        return await self._request("POST", "/subscriptions", json=payload)

    async def delete_webhook(self) -> Dict[str, Any]:
        return await self._request("DELETE", "/subscriptions")

    async def close(self):
        await self.client.aclose()
