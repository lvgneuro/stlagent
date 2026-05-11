from __future__ import annotations

import base64
import logging
import re
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.types import FSInputFile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram import html
from pathlib import Path
import tempfile

from bot.config import TELEGRAM_GROUP_ID

from bot.services.ai_service import get_ai_service
from bot.services.rivalli_search import rivalli_search
from bot.database import db

logger = logging.getLogger(__name__)

router = Router()


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return text


def is_sofa_request(text: str) -> bool:
    text_lower = text.lower()
    keywords = [
        "диван",
        "диваны",
        "кушетка",
        "угловой",
        "прямой",
        "модульн",
        "механизм",
        "еврокнижка",
        "аккордеон",
        "кровать",
        "спальн",
        "раскладн",
        "трансформер",
        "софа",
        "ривалли",
        "rivalli",
        "dakota",
        "порто",
        "орлеан",
        "лондон",
        "фарадей",
        "аруба",
        "амист",
        "амиsterdam",
        "бильбао",
        "блэквуд",
        "грэмми",
        "данте",
        "джимми",
        "дижон",
        "дискавери",
        "дублин",
        "женева",
        "каролина",
        "кембридж",
        "кинг",
        "клайд",
        "колорадо",
        "леннокс",
        "лерой",
        "люксор",
        "мадрид",
        "майя",
        "манхэттен",
        "маскот",
        "мистраль",
        "парма",
        "прато",
        "ричмонд",
        "сиэтл",
        "соло",
        "сомерсет",
        "сорренто",
        "темпо",
        "томас",
        "тулуза",
        "турин",
        "уолтер",
        "эльзас",
        "satellite",
        "space",
        "elias",
    ]
    return any(kw in text_lower for kw in keywords)


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    logger.info(f"Получен /start от {user_id}")
    name = message.from_user.full_name if message.from_user else " stranger"
    await message.answer("Интеллектуальный помощник по подбору мягкой мебели готов немедленно прийти к Вам на помощь!")


@router.message(Command("обновить_каталог", prefix="/"))
async def update_catalog_handler(message: Message) -> None:
    if message.from_user and message.from_user.id != 1696951195:
        await message.answer("У вас нет доступа к этой команде")
        return

    await message.answer("Обновляю каталог моделей с сайтов КАЛИНКА и ОПРАЙМ...")

    from bot.services.ai_service import load_catalog_urls

    await load_catalog_urls()
    from bot.services.ai_service import model_url_cache

    await message.answer(f"Каталог обновлён! Загружено {len(model_url_cache)} моделей.")


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
            details = await rivalli_search.fetch_sofa_details(sofa.url)
            if details:
                sofa.features = details
                sofa.description = None

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
        logger.error(f"Ошибка индексации: {e}")
        await message.answer(f"Ошибка индексации: {type(e).__name__}")


@router.message(Command("db_fix", prefix="/"))
async def db_fix_handler(message: Message) -> None:
    if message.from_user and message.from_user.id != 1696951195:
        await message.answer("У вас нет доступа к этой команде")
        return

    await message.answer("Исправляю схему БД...")
    try:
        from sqlalchemy import text

        engine = db.get_sync_engine()
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE messages ALTER COLUMN user_message TYPE TEXT")
            )
            conn.execute(
                text("ALTER TABLE messages ALTER COLUMN bot_response TYPE TEXT")
            )
            conn.execute(
                text("ALTER TABLE user_facts ALTER COLUMN fact_value TYPE TEXT")
            )
            conn.execute(text("ALTER TABLE user_facts ALTER COLUMN context TYPE TEXT"))
            conn.execute(
                text("ALTER TABLE user_images ALTER COLUMN description TYPE TEXT")
            )
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS conversations (id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, last_message_at TIMESTAMP DEFAULT NOW(), reminder_sent_15min INTEGER DEFAULT 0, reminder_sent_3h INTEGER DEFAULT 0, reminder_sent_1d INTEGER DEFAULT 0, last_reminder_at TIMESTAMP, topic TEXT, last_bot_message TEXT, created_at TIMESTAMP DEFAULT NOW())"
                )
            )
            conn.commit()
        await message.answer("✅ Схема БД обновлена. VARCHAR → TEXT")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {type(e).__name__}: {e}")


@router.message(Command("статистика_диваны", prefix="/"))
async def sofa_stats_handler(message: Message) -> None:
    if message.from_user and message.from_user.id != 1696951195:
        await message.answer("У вас нет доступа к этой команде")
        return

    count = await db.get_sofa_count()
    await message.answer(f"В базе данных {count} диванов Rivalli")


async def send_to_group(
    bot: Bot,
    client_info: str,
    interest: str | None,
    user_id: int,
) -> None:
    if not TELEGRAM_GROUP_ID:
        logger.warning("TELEGRAM_GROUP_ID не задан")
        return

    user_facts = await db.get_user_facts(user_id)
    client_name = user_facts.get("name", "")

    text = "📢 <b>Новая заявка!</b>\n\n"
    if client_name:
        text += f"Имя: {client_name}\n"
    text += f"Контакт: {client_info}\n"
    if interest:
        text += f"Интерес: {interest}\n"

    history = await db.get_user_messages(user_id, limit=10)
    if history:
        text += "\n<b>Диалог:</b>\n"
        for msg in history[-10:]:
            if msg.user_message and not msg.user_message.startswith("["):
                text += f"👤 {msg.user_message[:80]}\n"
            if msg.bot_response and not msg.bot_response.startswith("["):
                text += f"🤖 {msg.bot_response[:80]}\n"

    try:
        await bot.send_message(TELEGRAM_GROUP_ID, text)
        logger.info(f"Отправлена заявка в группу: {client_info[:50]}")
    except Exception as e:
        logger.error(f"Не удалось отправить в группу: {e}")


@router.message(Command("myid"))
async def myid_handler(message: Message, bot: Bot) -> None:
    chat = message.chat
    chat_type = chat.type if chat else "unknown"
    chat_id = chat.id if chat else "unknown"
    chat_title = chat.title if chat and hasattr(chat, "title") else ""

    await message.answer(f"Chat ID: {chat_id}\nType: {chat_type}\nTitle: {chat_title}")

    logger.info(
        f"Информация о чате: id={chat_id}, тип={chat_type}, название={chat_title}"
    )


@router.message(Command("мои_фото"))
async def my_photos_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    logger.info(f"Пользователь {user_id} запросил свои фото")

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
            logger.error(f"Ошибка отправки изображения {img.id}: {e}")

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


@router.message(F.content_type == "contact")
async def contact_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    contact = message.contact
    phone = contact.phone_number if contact else ""
    first_name = contact.first_name if contact else ""
    last_name = contact.last_name if contact else ""
    full_name = f"{first_name} {last_name}".strip() or first_name

    logger.info(f"Получен контакт от пользователя {user_id}: {phone} {full_name}")

    user_interest = await db.get_user_interest(user_id)

    contact_info = f"Контакт: {phone}"
    if full_name:
        contact_info += f" ({full_name})"
    if user_interest:
        contact_info += f"\nИнтерес: {user_interest}"

    await message.answer(
        f"Спасибо, {full_name or 'контакт получен'}! Мы свяжемся с вами в ближайшее время."
    )

    username_tg = message.from_user.username if message.from_user else None
    tg_link = f"@{username_tg}" if username_tg else "нет TG username"

    client_info = f"Телефон: {phone}"
    if full_name:
        client_info += f", Имя: {full_name}"
    client_info += f", TG: {tg_link}"

    await send_to_group(bot, client_info, user_interest, user_id)
    await db.mark_lead_sent(user_id)

    await db.save_message(
        user_id=user_id,
        username=message.from_user.username if message.from_user else None,
        first_name=message.from_user.first_name if message.from_user else None,
        user_message="[Контакт отправлен]",
        bot_response=contact_info,
    )


@router.message()
async def ai_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    first_name = message.from_user.first_name if message.from_user else None

    has_photo = message.photo is not None and len(message.photo) > 0

    if has_photo:
        logger.info(
            f"Получено фото от пользователя {user_id}, подпись: {message.caption!r}"
        )

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

                logger.info(f"Анализ изображения: {response[:100]}...")
                await message.answer(response)
                await analyzing_msg.delete()
                await db.touch_conversation(user_id, last_bot_message=response[:200])

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
            logger.error(f"Ошибка обработки изображения: {e}")
            await message.answer(f"Ошибка обработки изображения: {type(e).__name__}")
            return

    logger.info(f"Получено сообщение: {message.text[:50] if message.text else 'empty'}")
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
                    logger.error(f"Ошибка отправки изображения {image_id}: {e}")

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
                    logger.error(f"Ошибка отправки изображения {img.id}: {e}")
            return
        else:
            await message.answer(
                "У меня пока нет сохранённых фото. Отправь фото, и я его запомню!"
            )
            return

    if is_sofa_request(user_text):
        logger.info(f"Обнаружен запрос на диван: {user_text[:50]}")
        sofa_count = await db.get_sofa_count()
        logger.info(f"Количество диванов в БД: {sofa_count}")

        all_sofas = await db.get_all_sofas(limit=100)

        query_lower = user_text.lower()
        is_list_request = any(
            phrase in query_lower
            for phrase in [
                "какие",
                "список",
                "все",
                "перечисли",
                "покажи список",
                "какой диван",
                "какие диван",
                "что есть",
                "что знаешь",
            ]
        )

        if is_list_request and sofa_count > 0:
            unique_names = list(
                dict.fromkeys(
                    s.name
                    for s in all_sofas
                    if s.name and not s.name.endswith("Divany")
                )
            )
            response = f"Я вижу {len(unique_names)} диванов Rivalli:\n\n"
            for name in unique_names[:15]:
                response += f"• {name}\n"
            if len(unique_names) > 15:
                response += f"\n... и ещё {len(unique_names) - 15}"
            response += "\n\nХочешь подробнее про конкретную модель?"
            await message.answer(response)
            await db.touch_conversation(user_id, last_bot_message=response[:200])
            return

        if sofa_count > 0:
            search_words = query_lower.split()
            keywords = [w for w in search_words if len(w) > 3]

            if keywords:
                found_sofas = []
                for sofa in all_sofas:
                    name_lower = sofa.name.lower()
                    if any(kw in name_lower for kw in keywords):
                        found_sofas.append(sofa)
                    elif sofa.description and any(
                        kw in sofa.description.lower() for kw in keywords
                    ):
                        found_sofas.append(sofa)

                logger.info(f"Найдено {len(found_sofas)} диванов по ключевым словам")

            if found_sofas:
                first = found_sofas[0]
                details = await rivalli_search.fetch_sofa_details(first.url)

                if details:
                    response_text = f"<b>{first.name}</b>\n{details}\n\n🔗 {first.url}"
                else:
                    response_text = rivalli_search.format_search_results(
                        found_sofas[:5], user_text[:30]
                    )
                await message.answer(response_text)
                history = await db.get_user_messages(user_id, limit=20)
                conversation_history = []
                for msg in reversed(history):
                    if msg.user_message and msg.user_message.strip():
                        conversation_history.append(
                            {"role": "user", "content": msg.user_message}
                        )
                    if msg.bot_response and msg.bot_response.strip():
                        conversation_history.append(
                            {"role": "assistant", "content": msg.bot_response}
                        )
                thinking = await message.answer("Думаю...")
                follow_up = await get_ai_service().get_response(
                    f"Пользователь смотрит диван {first.name}. Расскажи коротко про цену, наличие в салонах Тюмени и почему именно эту модель стоит выбрать. Отвечай коротко, 1-2 абзаца.",
                    conversation_history,
                    user_id,
                )
                follow_up = follow_up.replace("\\n\\n", "\n\n").replace("\\n", "\n")
                follow_up = clean_html(follow_up)
                await message.answer(follow_up)
                await thinking.delete()
                try:
                    await db.save_message(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        user_message=user_text,
                        bot_response=response_text[:500],
                    )
                except Exception as e:
                    logger.error(f"Не удалось сохранить сообщение о диване: {e}")
                try:
                    await db.save_message(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        user_message=f"[Показан диван {first.name}]",
                        bot_response=follow_up[:5000],
                    )
                except Exception as e:
                    logger.error(f"Не удалось сохранить follow-up по дивану: {e}")

                await db.touch_conversation(
                    user_id, last_interest=f"Диван {first.name}"
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
    logger.info("Получение ответа от AI...")
    response = await get_ai_service().get_response(
        user_text, conversation_history, user_id
    )
    response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
    response = clean_html(response)

    logger.info(f"Отправка ответа: {response[:100]}...")
    await message.answer(response)

    await thinking_msg.delete()

    user_text_lower = user_text.lower()

    phone_pattern = re.compile(
        r"(\+?7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    )
    phone_match = phone_pattern.search(user_text)
    has_phone_keyword = any(
        word in user_text_lower
        for word in ["номер", "телефон", "звоните", "позвонить", "позвонит", "свяжитесь", "+7", "8-9", "8 9"]
    )

    if phone_match and has_phone_keyword:
        phone = phone_match.group()
        username_tg = message.from_user.username if message.from_user else None
        tg_link = f"@{username_tg}" if username_tg else "нет TG username"

        user_interest = await db.get_user_interest(user_id)
        client_info = f"Телефон: {phone}, TG: {tg_link}"

        await send_to_group(bot, client_info, user_interest, user_id)
        await db.mark_lead_sent(user_id)

    interest_keywords = ["диван", "кровать", "матрас", "кресло", "кушетка", "мебель"]
    detected_interest = None
    for kw in interest_keywords:
        if kw in user_text_lower:
            detected_interest = user_text[:100]
            break

    await db.touch_conversation(
        user_id,
        last_bot_message=response[:200],
        last_interest=detected_interest,
    )

    try:
        await db.save_message(
            user_id=user_id,
            username=username,
            first_name=first_name,
            user_message=user_text,
            bot_response=response[:5000],
        )
    except Exception as e:
        logger.error(f"Не удалось сохранить сообщение: {e}")
