from __future__ import annotations


class Bot:
    def __init__(self, token: str = None, **kwargs):
        self.token = token
        # We'll store parse_mode if provided via default
        self.parse_mode = None
        if "default" in kwargs:
            default = kwargs["default"]
            if hasattr(default, "parse_mode"):
                self.parse_mode = default.parse_mode

    # These methods will be overridden by MaxBot via monkey-patching in main.py
    async def send_message(self, chat_id: int, text: str, **kwargs):
        raise NotImplementedError

    async def send_photo(self, chat_id: int, photo, **kwargs):
        raise NotImplementedError

    async def download(self, file):
        raise NotImplementedError

    async def set_webhook(self, url: str):
        raise NotImplementedError

    async def delete_webhook(self):
        raise NotImplementedError
