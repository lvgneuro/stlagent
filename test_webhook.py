import json
from max_bot.main import max_message_to_aiogram, dp


async def test_handle_request():
    # Simulate a Max webhook payload
    update_data = {
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
            "body": {"mid": "mid123", "seq": 1, "text": "/start"},
        },
    }

    print("Testing webhook handler with payload:")
    print(json.dumps(update_data, indent=2))

    # Convert to aiogram Update
    try:
        aiogram_update = max_message_to_aiogram(update_data)
        print(f"\nConverted to aiogram Update: {aiogram_update}")
    except Exception as e:
        print(f"Conversion failed: {e}")
        return

    # Create a mock bot for testing
    class MockBot:
        async def send_message(self, chat_id, text):
            print(f"MockBot.send_message called: chat_id={chat_id}, text={text}")
            return {"ok": True}

    bot = MockBot()

    # Try to process the update
    try:
        await dp.feed_update(bot, aiogram_update)
        print("\nUpdate processed successfully!")
    except Exception as e:
        print(f"\nError processing update: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_handle_request())
