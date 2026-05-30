from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel


class User(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class Chat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class Message(BaseModel):
    message_id: int
    date: int
    chat: Chat
    from_user: User
    text: Optional[str] = None
    caption: Optional[str] = None
    contact: Optional[dict] = None
    photo: Optional[List[dict]] = None  # Simplified for now

    async def answer(self, text: str, **kwargs):
        # This is a placeholder - in real usage, the bot would be passed in
        # For our test, we'll just return the text
        # In main.py, we patch the Bot class to be MaxBot which handles sending
        # But for the fake, we need to have access to a bot instance
        # We'll store a reference to the bot if needed, but for now just return
        # The actual sending is handled by the patched Bot class in main.py
        # For the test, we'll need to mock this
        return {"ok": True, "result": {"message_id": self.message_id, "text": text}}


class Update(BaseModel):
    update_id: int
    message: Optional[Message] = None


# Minimal stubs for types used in the echo router
class FSInputFile:
    def __init__(self, path: str):
        self.path = path


class ReplyKeyboardMarkup:
    def __init__(self, keyboard, resize_keyboard=False, one_time_keyboard=False):
        self.keyboard = keyboard
        self.resize_keyboard = resize_keyboard
        self.one_time_keyboard = one_time_keyboard


class KeyboardButton:
    def __init__(self, text: str, request_contact=False):
        self.text = text
        self.request_contact = request_contact