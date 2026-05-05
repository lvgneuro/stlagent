from __future__ import annotations

import logging
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram import html

from bot.services.ai_service import get_ai_service
from bot.database import db

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    logger.info(f"Got /start from {user_id}")
    name = message.from_user.full_name if message.from_user else " stranger"
    await message.answer(f"Hello, {html.bold(name)}! How can I help you today?")


@router.message()
async def ai_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    first_name = message.from_user.first_name if message.from_user else None

    logger.info(f"Got message: {message.text[:50] if message.text else 'empty'}")
    user_text = message.text or ""

    history = await db.get_user_messages(user_id, limit=20)
    conversation_history = []
    for msg in reversed(history):
        conversation_history.append({"role": "user", "content": msg.user_message})
        conversation_history.append({"role": "assistant", "content": msg.bot_response})

    await message.answer("Думаю...")
    logger.info("Getting AI response...")
    response = await get_ai_service().get_response(user_text, conversation_history, user_id)
    response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
    logger.info(f"Sending response: {response[:100]}...")
    await message.answer(response)

    await db.save_message(
        user_id=user_id,
        username=username,
        first_name=first_name,
        user_message=user_text,
        bot_response=response,
    )