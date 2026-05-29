from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


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
    photo: Optional[list] = None


class Update(BaseModel):
    update_id: int
    message: Optional[Message] = None