from __future__ import annotations


def max_to_telegram_dict(update_data: dict) -> dict:
    """Convert Max platform webhook payload to a Telegram-format Update dict."""
    update_type = update_data.get("update_type") or update_data.get("type", "")
    timestamp = update_data.get("timestamp", 0)
    update_id = int(timestamp) // 1000 if timestamp else 0

    if update_type != "message_created":
        return {"update_id": update_id}

    msg = update_data.get("message", {})
    if not msg:
        return {"update_id": update_id}

    sender = msg.get("sender", {})
    recipient = msg.get("recipient", {})
    body = msg.get("body", {})

    chat_id = recipient.get("chat_id", 0)
    chat_type_raw = recipient.get("chat_type", "dialog")
    chat_type_map = {"dialog": "private", "group": "group", "channel": "channel"}
    chat_type = chat_type_map.get(chat_type_raw, "private")

    # For personal chats (dialog), use sender's user_id as chat.id.
    # recipient.chat_id may be a bot-internal ID, not the actual user.
    if chat_type == "private":
        chat_id = sender.get("user_id", chat_id)

    first_name = sender.get("first_name")
    if first_name is None:
        first_name = ""

    return {
        "update_id": update_id,
        "message": {
            "message_id": int(timestamp) // 1000,
            "date": int(timestamp) // 1000,
            "chat": {
                "id": chat_id,
                "type": chat_type,
            },
            "from": {
                "id": sender.get("user_id", 0),
                "is_bot": sender.get("is_bot", False),
                "first_name": first_name,
                "last_name": sender.get("last_name"),
                "username": sender.get("username"),
            },
            "text": body.get("text", ""),
        },
    }
