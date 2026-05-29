from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
import os

# Before importing the echo router, we need to make sure that when it imports aiogram,
# it gets our fake aiogram. We'll do this by inserting the path to our fake_aiogram
# at the beginning of sys.path and then removing the real aiogram from sys.modules if present.
# However, note that the real aiogram might be installed in the environment.
# We'll create a fake package named 'aiogram' in a temporary location and add its parent to sys.path.

fake_aiogram_path = os.path.join(os.path.dirname(__file__), 'fake_aiogram')
# Insert at the beginning so that our fake is found first.
if fake_aiogram_path not in sys.path:
    sys.path.insert(0, fake_aiogram_path)

# Now, if the real aiogram is already loaded, we need to remove it to avoid confusion.
# But we haven't imported it yet. However, just in case, we can delete the module.
modules_to_remove = [mod for mod in sys.modules if mod.startswith('aiogram')]
for mod in modules_to_remove:
    del sys.modules[mod]

from aiohttp import web

from max_bot.config import (
    MAX_BOT_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_PATH,
    HOST,
    PORT,
    TELEGRAM_GROUP_ID,
)
from max_bot.database import db
from max_bot.services.ai_service import get_ai_service
from max_bot.services.max_client import MaxBot

# Now import the echo router (which will import aiogram from our fake)
from max_bot.routers import echo

# We need to patch the Bot class in the fake aiogram to use our MaxBot.
# The echo router will create a Bot instance via `Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))`
# We want that Bot instance to actually be our MaxBot, but with the same interface.
# We can do this by monkey-patching the Bot class in the fake aiogram module.
import max_bot.fake_aiogram.bot as fake_bot_module

# Replace the Bot class in the fake module with a subclass that delegates to MaxBot.
# However, we need to keep the same constructor signature.
# We'll create a wrapper class that inherits from the fake Bot (which is just a stub) and then
# override the methods to call MaxBot.
# But note: the echo router also uses `Bot` to call `set_webhook` and `delete_webhook`.
# We'll make our wrapper such that when Bot(...) is called, it returns an instance of MaxBot
# but with the same interface as the fake Bot (so that isinstance checks pass?).
# Actually, the echo router does not do isinstance checks on Bot; it just calls methods.
# So we can simply replace the Bot class in the fake module with our MaxBot class.
# However, the Bot class in the fake module is also used for type hints? Not really.
# Let's do: fake_bot_module.Bot = MaxBot
# But we need to ensure that MaxBot has the same constructor signature as the fake Bot.
# The fake Bot's __init__ is: def __init__(self, token: str = None, **kwargs)
# Our MaxBot's __init__ is: def __init__(self, token: str):
# We can adjust MaxBot to accept **kwargs and ignore them, or we can create a subclass.
# Let's adjust MaxBot in max_client.py to accept **kwargs and ignore extra.
# We'll do that in a moment.

# For now, we'll assume we have adjusted MaxBot.
# We'll replace the Bot class in the fake module with MaxBot.
fake_bot_module.Bot = MaxBot

# Also, we need to patch the Dispatcher? The echo router does not use Dispatcher directly;
# it uses the router and then in main.py we create a Dispatcher and include the router.
# We'll keep using our own Dispatcher from the fake aiogram (which we will import below).
# But note: the echo router does not import Dispatcher.

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# We'll use the Dispatcher from our fake aiogram
from max_bot.fake_aiogram.dispatcher import Dispatcher

dp = Dispatcher()
dp.include_router(echo.router)

MOSCOW_TZ = timezone(timedelta(hours=3))
YEKATERINBURG_TZ = timezone(timedelta(hours=5))


def _is_night_time() -> bool:
    now = datetime.now(YEKATERINBURG_TZ)
    return now.hour >= 23 or now.hour < 9


async def _run_indexing(bot: MaxBot) -> None:
    try:
        from max_bot.services.rivalli_parser import run_indexing

        logger.info("Запуск ежедневной индексации диванов...")
        sofas = await run_indexing()

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
        logger.info(f"Ежедневная индексация завершена. Всего диванов: {count}")

        admin_id = 1696951195  # Keep same admin ID; adjust if needed for Max
        try:
            await bot.send_message(admin_id, f"✅ Ежедневная индексация диванов завершена. Всего в базе: {count}")
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Ошибка ежедневной индексации: {e}")


async def daily_sofa_indexing(bot: MaxBot) -> None:
    while True:
        now_wall = __import__("datetime").datetime.now(MOSCOW_TZ)
        target = now_wall.replace(hour=9, minute=0, second=0, microsecond=0)
        if now_wall.hour >= 9:
            target += timedelta(days=1)
        seconds_until = (target - now_wall).total_seconds()
        logger.info(
            f"Следующая индексация через {seconds_until / 3600:.1f} часов в {target}"
        )
        await asyncio.sleep(seconds_until)
        await _run_indexing(bot)


REMINDER_INTERVALS = ["15min", "3h", "1d"]
REMINDER_CHECK_PERIOD = 60


async def reminder_worker(bot: MaxBot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            if _is_night_time():
                logger.debug("Ночное время — напоминания отключены")
            else:
                for interval in REMINDER_INTERVALS:
                    pending = await db.get_pending_reminders([interval])
                    for user_id, topic, last_msg in pending:
                        if user_id == 1696951195:
                            continue
                        if last_msg:
                            prompt = f'Клиент не ответил после того как бот отправил:\n"{last_msg[:500]}"\n\nЕсли topic: {topic or "неизвестно"}.\n\nОтправь клиенту мягкое напоминание, 1-2 предложения. Не дави, не продавай агрессивно. Например: «Не нашли то, что искали? Я на связи, если появятся вопросы.»'
                        else:
                            prompt = "Отправь клиенту мягкое напоминание, 1-2 предложения. Не дави, не продавай агрессивно."

                        response = await get_ai_service().get_response(
                            prompt, [], user_id
                        )
                        response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
                        try:
                            await bot.send_message(user_id, response[:500])
                            await db.mark_reminder_sent(user_id, interval)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Ошибка воркера напоминаний: {e}")
        await asyncio.sleep(REMINDER_CHECK_PERIOD)


LEAD_UPDATE_CHECK_PERIOD = 60


async def lead_update_worker(bot: MaxBot) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            from datetime import timedelta
            from sqlalchemy import select, and_

            async with db._session_factory() as session:
                from max_bot.database import ConversationModel

                one_minute_ago = datetime.now() - timedelta(minutes=1)
                stmt = select(ConversationModel).where(
                    and_(
                        ConversationModel.lead_sent_at.isnot(None),
                        ConversationModel.last_lead_update_at.is_(None),
                        ConversationModel.lead_sent_at < one_minute_ago,
                    )
                )
                result = await session.execute(stmt)
                convs = result.scalars().all()

                for conv in convs:
                    if conv.user_id == 1696951195:
                        continue

                    new_messages = await db.get_messages_after_lead(
                        conv.user_id, conv.lead_sent_at
                    )
                    if new_messages and TELEGRAM_GROUP_ID:
                        text = "🔄 <b>Обновление по заявке</b>\n\n"
                        for msg in new_messages:
                            if msg.user_message and not msg.user_message.startswith(
                                "["
                            ):
                                text += f"👤 {msg.user_message[:80]}\n"
                            if msg.bot_response and not msg.bot_response.startswith(
                                "["
                            ):
                                text += f"🤖 {msg.bot_response[:80]}\n"

                        try:
                            await bot.send_message(TELEGRAM_GROUP_ID, text)
                            conv.last_lead_update_at = conv.lead_sent_at
                            await session.commit()
                            logger.info(
                                f"Отправлено обновление по заявке для пользователя {conv.user_id}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Не удалось отправить обновление по заявке: {e}"
                            )

        except Exception as e:
            logger.error(f"Ошибка воркера обновлений по заявкам: {e}")
        await asyncio.sleep(LEAD_UPDATE_CHECK_PERIOD)


async def on_startup(bot: MaxBot) -> None:
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Вебхук установлен на {WEBHOOK_URL}")

    sofa_count = await db.get_sofa_count()
    logger.info(f"Количество диванов в БД: {sofa_count}")

    logger.info("В БД проиндексировано 82 дивана. Пропуск начальной индексации.")

    asyncio.create_task(daily_sofa_indexing(bot))
    asyncio.create_task(reminder_worker(bot))
    asyncio.create_task(lead_update_worker(bot))


async def on_shutdown(bot: MaxBot) -> None:
    await bot.delete_webhook()
    logger.info("Вебхук удалён")


def max_message_to_aiogram(update_data: dict):
    """
    Convert a Max webhook payload to an aiogram.types.Update object (from our fake aiogram).
    """
    from max_bot.fake_aiogram.types import Update as AiogramUpdate, Message, User, Chat, Contact, PhotoSize

    update_type = update_data.get("update_type")
    update_id = update_data.get("update_id", 0)

    # We only handle message updates for now.
    if update_type != "message":
        return AiogramUpdate(update_id=update_id, message=None)

    msg = update_data.get("message", {})
    # User
    from_user_data = msg.get("from", {})
    from_user = User(
        id=from_user_data.get("id", 0),
        is_bot=from_user_data.get("is_bot", False),
        first_name=from_user_data.get("first_name"),
        last_name=from_user_data.get("last_name"),
        username=from_user_data.get("username"),
        language_code=from_user_data.get("language_code"),
    )
    # Chat
    chat_data = msg.get("chat", {})
    chat = Chat(
        id=chat_data.get("id", 0),
        type=chat_data.get("type", "private"),
        title=chat_data.get("title"),
        username=chat_data.get("username"),
        first_name=chat_data.get("first_name"),
        last_name=chat_data.get("last_name"),
    )
    # Contact
    contact_data = msg.get("contact")
    contact = None
    if contact_data:
        contact = Contact(
            phone_number=contact_data.get("phone_number", ""),
            first_name=contact_data.get("first_name"),
            last_name=contact_data.get("last_name"),
            user_id=contact_data.get("user_id"),
            vcard=contact_data.get("vcard"),
        )
    # Photo
    photo_data = msg.get("photo", [])
    photo = []
    for p in photo_data:
        photo.append(
            PhotoSize(
                file_id=p.get("file_id", ""),
                width=p.get("width", 0),
                height=p.get("height", 0),
                file_size=p.get("file_size"),
            )
        )
    # Build Message
    message = Message(
        message_id=msg.get("message_id", 0),
        date=msg.get("date", 0),
        chat=chat,
        from_user=from_user,
        text=msg.get("text"),
        caption=msg.get("caption"),
        contact=contact,
        photo=photo if photo else None,
    )
    return AiogramUpdate(update_id=update_id, message=message)


async def main() -> None:
    logger.info("Запуск бота в режиме вебхука...")
    if not MAX_BOT_TOKEN:
        raise ValueError("MAX_BOT_TOKEN is not set")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set")

    await db.init_db()
    logger.info("База данных инициализирована")

    from max_bot.services.ai_service import load_catalog_urls
    await load_catalog_urls()

    bot = MaxBot(token=MAX_BOT_TOKEN)
    await on_startup(bot)

    app = web.Application()
    app["bot"] = bot

    async def handle_request(request):
        try:
            update_data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")
        # Convert Max update to aiogram Update (using our fake types)
        try:
            aiogram_update = max_message_to_aiogram(update_data)
        except Exception as e:
            logger.error(f"Failed to convert Max update: {e}")
            return web.Response(status=500, text="Update conversion error")
        # Feed to dp
        try:
            await dp.feed_update(bot, aiogram_update)
        except Exception as e:
            logger.error(f"Error while processing update: {e}")
            return web.Response(status=500, text="Processing error")
        return web.Response()

    app.router.add_post(WEBHOOK_PATH, handle_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    logger.info(f"Вебхук-сервер запущен на http://{HOST}:{PORT}{WEBHOOK_PATH}")

    try:
        await asyncio.Event().wait()
    finally:
        await on_shutdown(bot)
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())