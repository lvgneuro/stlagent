from __future__ import annotations

import base64
import logging
import re
from aiogram import Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram import html
from io import BytesIO
from pathlib import Path
import tempfile

from bot.services.ai_service import get_ai_service
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


@router.message(Command("мои_фото"))
async def my_photos_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    logger.info(f"User {user_id} requested their photos")
    
    images = await db.get_user_images(user_id, limit=20)
    
    if not images:
        await message.answer("У меня пока нет сохранённых изображений. Отправь мне фото, и я его запомню!")
        return
    
    await message.answer(f"У меня сохранено {len(images)} изображений. Показываю последние 5...")
    
    for img in images[:5]:
        try:
            from aiogram.types import FSInputFile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", mode="wb") as tmp:
                tmp.write(img.image_data)
                tmp_path = tmp.name
            photo = FSInputFile(tmp_path)
            if img.description:
                await bot.send_photo(user_id, photo, caption=f"Изображение #{img.id}")
            else:
                await bot.send_photo(user_id, photo)
            Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Error sending image {img.id}: {e}")
    
    await message.answer(
        "Чтобы посмотреть конкретное изображение, напиши: /фото 1 (где 1 - номер изображения)"
    )


@router.message(Command("фото"))
async def show_photo_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Укажи номер изображения. Например: /фото 1")
        return
    
    try:
        image_id = int(parts[1])
    except ValueError:
        await message.answer("Номер изображения должен быть числом. Например: /фото 1")
        return
    
    img = await db.get_image_by_id(image_id, user_id)
    
    if not img:
        await message.answer(f"Изображение #{image_id} не найдено. Посмотреть список: /мои_фото")
        return
    
    try:
        from aiogram.types import FSInputFile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", mode="wb") as tmp:
            tmp.write(img.image_data)
            tmp_path = tmp.name
        photo = FSInputFile(tmp_path)
        caption = f"Изображение #{img.id}"
        if img.description:
            caption += f"\nОписание: {img.description}"
        await bot.send_photo(user_id, photo, caption=caption)
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"Error sending image {image_id}: {e}")
        await message.answer(f"Не удалось отправить изображение: {type(e).__name__}")


@router.message()
async def ai_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    first_name = message.from_user.first_name if message.from_user else None

    has_photo = message.photo is not None and len(message.photo) > 0
    
    if has_photo:
        logger.info(f"Got photo from user {user_id}, caption: {message.caption!r}")
        
        try:
            photo = message.photo[-1]
            file = await bot.download(photo)
            image_bytes = file.read()
            image_data = base64.b64encode(image_bytes).decode("utf-8")
            
            await db.save_image(
                user_id=user_id,
                image_data=image_bytes,
                file_id=photo.file_id,
                description=message.caption,
            )
            
            user_text = (message.caption or "").strip()
            
            if user_text.strip():
                await message.answer("Редактирую изображение...")
                ai_service = get_ai_service()
                response = await ai_service.edit_image(image_data, user_text)
                
                if "error" in response:
                    detail = response.get("detail", "")
                    await message.answer(f"Ошибка: {response['error']} {detail}")
                else:
                    await message.answer(response["url"])
                    response = f"[Изображение отредактировано: {user_text}]"
                
                await db.save_message(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    user_message=f"[Фото + запрос: {user_text}]",
                    bot_response=response,
                )
            else:
                await message.answer("Анализирую изображение...")
                ai_service = get_ai_service()
                response = await ai_service.analyze_image(image_data, "Опиши что ты видишь на этом изображении")
                
                response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
                response = clean_html(response)
                
                logger.info(f"Image analysis: {response[:100]}...")
                await message.answer(response)
                
                user_text = "[Изображение]"
                await db.save_message(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    user_message=user_text,
                    bot_response=response,
                )
            return
        except Exception as e:
            logger.error(f"Image handling error: {e}")
            await message.answer(f"Ошибка обработки изображения: {type(e).__name__}")
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