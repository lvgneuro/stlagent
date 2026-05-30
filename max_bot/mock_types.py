from __future__ import annotations

class MockFSInputFile:
    def __init__(self, path: str):
        self.path = path

class MockPhotoSize:
    def __init__(self, file_id: str, width: int = 0, height: int = 0, file_size: int = 0):
        self.file_id = file_id
        self.width = width
        self.height = height
        self.file_size = file_size

class MockUser:
    def __init__(self, user_dict: dict):
        self.id = user_dict.get('id') if user_dict else None
        self.is_bot = user_dict.get('is_bot', False) if user_dict else False
        self.first_name = user_dict.get('first_name') if user_dict else None
        self.last_name = user_dict.get('last_name') if user_dict else None
        self.username = user_dict.get('username') if user_dict else None
        self.language_code = user_dict.get('language_code') if user_dict else None
        self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

class MockChat:
    def __init__(self, chat_dict: dict):
        self.id = chat_dict.get('id') if chat_dict else None
        self.type = chat_dict.get('type') if chat_dict else None
        self.title = chat_dict.get('title') if chat_dict else None
        self.username = chat_dict.get('username') if chat_dict else None
        self.first_name = chat_dict.get('first_name') if chat_dict else None
        self.last_name = chat_dict.get('last_name') if chat_dict else None

class MockMessage:
    def __init__(self, message_dict: dict):
        self.message_id = message_dict.get('message_id')
        self.date = message_dict.get('date')
        self.chat = MockChat(message_dict.get('chat')) if message_dict.get('chat') else None
        self.from_user = MockUser(message_dict.get('from')) if message_dict.get('from') else None
        self.text = message_dict.get('text')
        self.caption = message_dict.get('caption')
        self.contact = message_dict.get('contact')  # This is a dict as sent by Max
        self.photo = [MockPhotoSize(**p) for p in message_dict.get('photo', [])] if message_dict.get('photo') else None
        # We might need to add other attributes as needed, but let's start with these.

class MockUpdate:
    def __init__(self, update_dict: dict):
        self.update_id = update_dict.get('update_id')
        self.message = MockMessage(update_dict.get('message')) if update_dict.get('message') else None
        # We can add other update types (edited_message, channel_post, etc.) if needed
        # For now, we only handle regular messages.

# We'll also need to mock the bot's methods that are used in the echo router.
# We'll create a MockBot class that wraps our MaxBot and provides the same interface as aiogram's Bot.
# This will be in max_client.py or a separate file. For now, we'll assume we have a MaxBot with the needed methods.