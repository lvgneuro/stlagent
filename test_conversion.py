import sys

sys.path.insert(0, "max_bot")
from max_bot.main import max_message_to_aiogram

# Sample Max payload
sample = {
    "update_type": "message_created",
    "timestamp": 1717000000000,
    "message": {
        "recipient": {"chat_id": 12345, "chat_type": "dialog"},
        "sender": {
            "user_id": 54321,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "is_bot": False,
        },
        "body": {"mid": "mid123", "seq": 1, "text": "Hello"},
    },
}

try:
    result = max_message_to_aiogram(sample)
    print("Success:", result)
    print("Update ID:", result.update_id)
    print("Message ID:", result.message.message_id)
    print("Date:", result.message.date)
    print("Chat ID:", result.message.chat.id)
    print("Chat Type:", result.message.chat.type)
    print("From User ID:", result.message.from_user.id)
    print("Text:", result.message.text)
except Exception as e:
    print("Error:", str(e))
    import traceback

    traceback.print_exc()
