from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Union, Optional, Callable, Any

# --- Basic types ---
class User:
    def __init__(self, id: int = 0, is_bot: bool = False, first_name: str = None,
                 last_name: str = None, username: str = None, language_code: str = None):
        self.id = id
        self.is_bot = is_bot
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.language_code = language_code
        self.full_name = f"{first_name or ''} {last_name or ''}".strip()

class Chat:
    def __init__(self, id: int = 0, type: str = "private", title: str = None,
                 username: str = None, first_name: str = None, last_name: str = None):
        self.id = id
        self.type = type
        self.title = title
        self.username = username
        self.first_name = first_name
        self.last_name = last_name

class ChatMemberUpdated:
    pass

class Contact:
    def __init__(self, phone_number: str = "", first_name: str = None,
                 last_name: str = None, user_id: int = None, vcard: str = None):
        self.phone_number = phone_number
        self.first_name = first_name
        self.last_name = last_name
        self.user_id = user_id
        self.vcard = vcard

class PhotoSize:
    def __init__(self, file_id: str = "", width: int = 0, height: int = 0,
                 file_size: int = None):
        self.file_id = file_id
        self.width = width
        self.height = height
        self.file_size = file_size

class Voice:
    pass

class Animation:
    pass

class Video:
    pass

class Audio:
    pass

class Document:
    pass

class Sticker:
    pass

class Venue:
    pass

class Location:
    pass

class Poll:
    pass

class Dice:
    pass

class Message:
    def __init__(self, message_id: int = 0, date: int = 0, chat: Chat = None,
                 from_user: User = None, text: str = None,
                 caption: str = None, contact: Contact = None,
                 photo: List[PhotoSize] = None, voice: Voice = None,
                 animation: Animation = None, video: Video = None,
                 audio: Audio = None, document: Document = None,
                 sticker: Sticker = None, venue: Venue = None,
                 location: Location = None, poll: Poll = None,
                 dice: Dice = None, caption_entities=None,
                 content_type: str = None):
        self.message_id = message_id
        self.date = date
        self.chat = chat
        self.from_user = from_user
        self.text = text
        self.caption = caption
        self.contact = contact
        self.photo = photo
        self.voice = voice
        self.animation = animation
        self.video = video
        self.audio = audio
        self.document = document
        self.sticker = sticker
        self.venue = venue
        self.location = location
        self.poll = poll
        self.dice = dice
        self.caption_entities = caption_entities
        if content_type is None:
            if contact is not None:
                content_type = "contact"
            elif photo is not None and len(photo) > 0:
                content_type = "photo"
            elif voice is not None:
                content_type = "voice"
            elif animation is not None:
                content_type = "animation"
            elif video is not None:
                content_type = "video"
            elif audio is not None:
                content_type = "audio"
            elif document is not None:
                content_type = "document"
            elif sticker is not None:
                content_type = "sticker"
            elif venue is not None:
                content_type = "venue"
            elif location is not None:
                content_type = "location"
            elif poll is not None:
                content_type = "poll"
            elif dice is not None:
                content_type = "dice"
            elif text is not None:
                content_type = "text"
            elif caption is not None:
                content_type = "caption"
            else:
                content_type = "unknown"
        self.content_type = content_type

class FSInputFile:
    def __init__(self, path: Union[str, Path]):
        self.path = str(path)

class ReplyKeyboardMarkup:
    def __init__(self, keyboard: List[List[dict]] = None,
                 resize_keyboard: bool = False,
                 one_time_keyboard: bool = False,
                 selective: bool = False,
                 input_field_placeholder: str = None,
                 is_persistent: bool = False):
        self.keyboard = keyboard or []
        self.resize_keyboard = resize_keyboard
        self.one_time_keyboard = one_time_keyboard
        self.selective = selective
        self.input_field_placeholder = input_field_placeholder
        self.is_persistent = is_persistent

class KeyboardButton:
    def __init__(self, text: str, request_contact: bool = False,
                 request_location: bool = False,
                 request_poll: dict = None,
                 web_app: dict = None):
        self.text = text
        self.request_contact = request_contact
        self.request_location = request_location
        self.request_poll = request_poll
        self.web_app = web_app