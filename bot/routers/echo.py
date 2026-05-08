from __future__ import annotations

import base64
import logging
import re
from aiogram import Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.types import FSInputFile
from aiogram import html
from pathlib import Path
import tempfile

from bot.services.ai_service import get_ai_service
from bot.services.rivalli_search import rivalli_search
from bot.database import db

logger = logging.getLogger(__name__)

router = Router()


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return text


def is_sofa_request(text: str) -> bool:
    text_lower = text.lower()
    keywords = [
        "диван", "диваны", "кушетка", "угловой", "прямой", "модульн",
        "механизм", "еврокнижка", "аккордеон", "кровать", "спальн",
        "раскладн", "трансформер", "софа", "ривалли", "rivalli",
        "dakar", "dakota", "порто", "орлеан", "лондон", "фарадей",
        "аруба", "амист", "амиsterdam", "бильбао", "блэквуд", "грэмми",
        "данте", "джимми", "дижон", "дискавери", "дублин", "женева",
        "каролина", "кембридж", "кинг", "клайд", "колорадо", "леннокс",
        "лерой", "люксор", "мадрид", "майя", "манхэттен", "маскот",
        "мистраль", "парма", "прато", "ричмонд", "сиэтл", "соло",
        "сомерсет", "сорренто", "темпо", "томас", "тулуза", "турин",
        "уолтер", "эльзас", "satellite", "space", "elias",
    ]
    return any(kw in text_lower for kw in keywords)


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    logger.info(f"Got /start from {user_id}")
    name = message.from_user.full_name if message.from_user else " stranger"
    await message.answer(f"Hello, {html.bold(name)}! How can I help you today?")


@router.message(Command("индексация_диваны", prefix="/"))
async def index_sofas_handler(message: Message) -> None:
    if message.from_user and message.from_user.id != 1696951195:
        await message.answer("У вас нет доступа к этой команде")
        return

    await message.answer("Начинаю индексацию каталога диванов Rivalli...")

    from bot.services.rivalli_parser import run_indexing

    try:
        sofas = await run_indexing()
        await message.answer(f"Собрано {len(sofas)} диванов. Сохраняю в базу...")

        for sofa in sofas:
            await db.save_sofa(
                slug=sofa.slug,
                name=sofa.name,
                url=sofa.url,
                category=sofa.category,
                description=sofa.description,
                features=sofa.features,
                image_urls=",".join(sofa.image_urls) if sofa.image_urls else None,
            )

        count = await db.get_sofa_count()
        await message.answer(f"✅ Индексация завершена! Всего в базе: {count} диванов")
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        await message.answer(f"Ошибка индексации: {type(e).__name__}")


@router.message(Command("статистика_диваны", prefix="/"))
async def sofa_stats_handler(message: Message) -> None:
    if message.from_user and message.from_user.id != 1696951195:
        await message.answer("У вас нет доступа к этой команде")
        return

    count = await db.get_sofa_count()
    await message.answer(f"В базе данных {count} диванов Rivalli")


@router.message(Command("мои_фото"))
async def my_photos_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    logger.info(f"User {user_id} requested their photos")

    images = await db.get_user_images(user_id, limit=20)

    if not images:
        await message.answer(
            "У меня пока нет сохранённых изображений. Отправь мне фото, и я его запомню!"
        )
        return

    await message.answer(
        f"У меня сохранено {len(images)} изображений. Показываю последние 5..."
    )

    for img in images[:5]:
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".jpg", mode="wb"
            ) as tmp:
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
        await message.answer(
            f"Изображение #{image_id} не найдено. Посмотреть список: /мои_фото"
        )
        return

    try:
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


@router.message(Command("диалоги"))
async def recent_dialogs_handler(message: Message) -> None:
    if message.from_user and message.from_user.id != 1696951195:
        await message.answer("У вас нет доступа к этой команде")
        return

    await message.answer("Загружаю последние диалоги...")
    dialogs = await db.get_recent_messages(limit=30)

    if not dialogs:
        await message.answer("Нет диалогов")
        return

    grouped = {}
    for d in dialogs:
        uid = d["user_id"]
        if uid not in grouped:
            grouped[uid] = {"first_name": d["first_name"], "messages": []}
        grouped[uid]["messages"].append(d)

    text = f"Последние 30 сообщений от {len(grouped)} пользователей:\n\n"

    for uid, data in list(grouped.items())[:10]:
        name = data["first_name"] or f"ID:{uid}"
        msgs = data["messages"]
        text += f"👤 {name} (ID: {uid}):\n"
        for m in msgs[:3]:
            text += f"  Q: {m['message']}...\n"
            text += f"  A: {m['response']}...\n\n"

    await message.answer(text)


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
                editing_msg = await message.answer("Редактирую изображение...")
                ai_service = get_ai_service()
                response = await ai_service.edit_image(image_data, user_text)

                if "error" in response:
                    detail = response.get("detail", "")
                    await message.answer(f"Ошибка: {response['error']} {detail}")
                    await editing_msg.delete()
                else:
                    await message.answer(response["url"])
                    response = f"[Изображение отредактировано: {user_text}]"
                    await editing_msg.delete()

                await db.save_message(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    user_message=f"[Фото + запрос: {user_text}]",
                    bot_response=response,
                )
            else:
                analyzing_msg = await message.answer("Анализирую изображение...")
                ai_service = get_ai_service()
                response = await ai_service.analyze_image(
                    image_data, "Опиши что ты видишь на этом изображении"
                )

                response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
                response = clean_html(response)

                logger.info(f"Image analysis: {response[:100]}...")
                await message.answer(response)
                await analyzing_msg.delete()

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

    photo_request = re.search(
        r"/фото\s*(\d+)|покажи.*фото|отправь.*фото", user_text.lower()
    )
    if photo_request:
        image_id = int(photo_request.group(1)) if photo_request.group(1) else None
        if image_id:
            img = await db.get_image_by_id(image_id, user_id)
            if img:
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".jpg", mode="wb"
                    ) as tmp:
                        tmp.write(img.image_data)
                        tmp_path = tmp.name
                    photo = FSInputFile(tmp_path)
                    await bot.send_photo(
                        user_id, photo, caption=f"Изображение #{img.id}"
                    )
                    Path(tmp_path).unlink(missing_ok=True)
                    return
                except Exception as e:
                    logger.error(f"Error sending image {image_id}: {e}")

        images = await db.get_user_images(user_id, limit=5)
        if images:
            for img in images[:5]:
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".jpg", mode="wb"
                    ) as tmp:
                        tmp.write(img.image_data)
                        tmp_path = tmp.name
                    photo = FSInputFile(tmp_path)
                    await bot.send_photo(
                        user_id, photo, caption=f"Изображение #{img.id}"
                    )
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.error(f"Error sending image {img.id}: {e}")
            return
        else:
            await message.answer(
                "У меня пока нет сохранённых фото. Отправь фото, и я его запомню!"
            )
            return

    if is_sofa_request(user_text):
        logger.info(f"Sofa request detected: {user_text[:50]}")
        sofa_count = await db.get_sofa_count()
        logger.info(f"Sofa count in DB: {sofa_count}")
        if sofa_count > 0:
            search_query = user_text.lower()
            stop_words = ["диван", "про", "что", "знаешь", "какой", "у", "от", "есть", "ли", "можешь", "предложить", "дорогое", "из", "фабрики", "какой", "какая", "ривалли", "rivalli", "калинка", "опрайм", "опраим"]
            for word in stop_words:
                search_query = search_query.replace(word, "")

            import re
            search_query = re.sub(r'[^\w\s]', '', search_query).strip()

            if len(search_query) >= 2:
                logger.info(f"Searching Rivalli with: '{search_query}'")
                results = await rivalli_search.search(search_query, limit=5)
                logger.info(f"Search results: {len(results)}")
                if results:
                    response_text = rivalli_search.format_search_results(results, search_query)
                    await message.answer(response_text)
                    await db.save_message(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        user_message=user_text,
                        bot_response=response_text[:500],
                    )
                    return
        else:
            await message.answer(
                "Каталог диванов Rivalli ещё не проиндексирован. "
                "Напишите администратору, чтобы запустить /индексация_диваны"
            )
            return

    history = await db.get_user_messages(user_id, limit=20)
    conversation_history = []
    for msg in reversed(history):
        if msg.user_message and msg.user_message.strip():
            conversation_history.append({"role": "user", "content": msg.user_message})
        if msg.bot_response and msg.bot_response.strip():
            conversation_history.append(
                {"role": "assistant", "content": msg.bot_response}
            )

    thinking_msg = await message.answer("Думаю...")
    logger.info("Getting AI response...")
    response = await get_ai_service().get_response(
        user_text, conversation_history, user_id
    )
    response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
    response = clean_html(response)
    logger.info(f"Sending response: {response[:100]}...")
    await message.answer(response)
    await thinking_msg.delete()

    await db.save_message(
        user_id=user_id,
        username=username,
        first_name=first_name,
        user_message=user_text,
        bot_response=response,
    )
