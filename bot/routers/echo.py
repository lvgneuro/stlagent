from __future__ import annotations

import base64
import io
import logging
import re
from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram import html

from bot.services.ai_service import get_ai_service, AIService
from bot.database import db

logger = logging.getLogger(__name__)

router = Router()


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return text


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    logger.info(f"Got /start from {user_id}")
    name = message.from_user.full_name if message.from_user else " stranger"
    await message.answer(f"Hello, {html.bold(name)}! How can I help you today?")


@router.message()
async def ai_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    first_name = message.from_user.first_name if message.from_user else None

    has_photo = message.photo is not None and len(message.photo) > 0
    
    if has_photo:
        logger.info(f"Got photo from user {user_id}")
        await message.answer("Анализирую изображение...")
        
        try:
            photo = message.photo[-1]
            file = await bot.download(photo)
            image_data = base64.b64encode(file.read()).decode("utf-8")
            
            ai_service = get_ai_service()
            response = await ai_service.analyze_image(image_data, message.caption or "Опиши что ты видишь на этом изображении")
            
            response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
            response = clean_html(response)
            
            logger.info(f"Image analysis: {response[:100]}...")
            await message.answer(response)
            
            user_text = message.caption or "[Изображение]"
            await db.save_message(
                user_id=user_id,
                username=username,
                first_name=first_name,
                user_message=user_text,
                bot_response=response,
            )
            return
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            await message.answer(f"Не удалось проанализировать изображение: {type(e).__name__}")
            return

    logger.info(f"Got message: {message.text[:50] if message.text else 'empty'}")
    user_text = message.text or ""
    
    if not user_text.strip():
        await message.answer("Не могу ответить на пустое сообщение. Напиши что-нибудь.")
        return

    history = await db.get_user_messages(user_id, limit=20)
    conversation_history = []
    for msg in reversed(history):
        if msg.user_message and msg.user_message.strip():
            conversation_history.append({"role": "user", "content": msg.user_message})
        if msg.bot_response and msg.bot_response.strip():
            conversation_history.append({"role": "assistant", "content": msg.bot_response})

    await message.answer("Думаю...")
    logger.info("Getting AI response...")
    response = await get_ai_service().get_response(user_text, conversation_history, user_id)
    response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
    response = clean_html(response)
    logger.info(f"Sending response: {response[:100]}...")
    await message.answer(response)

    await db.save_message(
        user_id=user_id,
        username=username,
        first_name=first_name,
        user_message=user_text,
        bot_response=response,
    )