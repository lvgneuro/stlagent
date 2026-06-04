# ruff: noqa: E402
from __future__ import annotations

import sys
import os

# --- Replace aiogram with our fake ---
# Add the directory containing the fake_aiogram package to sys.path
# (the directory that contains the fake_aiogram folder)
fake_aiogram_dir = os.path.dirname(__file__)  # E:\ТГ-агент\max_bot
if fake_aiogram_dir not in sys.path:
    sys.path.insert(0, fake_aiogram_dir)

# Remove any real aiogram modules that might have been loaded.
modules_to_remove = [mod for mod in sys.modules if mod.startswith("aiogram")]
for mod in modules_to_remove:
    del sys.modules[mod]

# Import the fake aiogram package
import fake_aiogram

# Replace the aiogram module with our fake
sys.modules["aiogram"] = fake_aiogram
# --- End replacement ---

import asyncio
import logging
from datetime import datetime, timedelta, timezone

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

from max_bot.services.max_client import MaxBot

# Now import the echo router (which will import aiogram from our fake, now sys.modules['aiogram'])
from max_bot.routers import echo

# We need to patch the Bot class in the aiogram module to use our MaxBot.
import aiogram.bot as aiogram_bot_module

# Replace the Bot class in the aiogram module with MaxBot.
# We need to make sure MaxBot has the same signature as the fake Bot.
# The fake Bot's __init__ is: def __init__(self, token: str = None, **kwargs)
# Our MaxBot's __init__ is: def __init__(self, token: str):
# We'll adjust MaxBot to accept **kwargs and ignore them.
# We'll do that by modifying the MaxBot class in max_client.py to accept **kwargs.
# But let's do it here by creating a wrapper if needed.
# However, let's first check if MaxBot already accepts **kwargs.
# We'll look at max_client.py: it does accept **kwargs in __init__.
# So we can simply assign:
aiogram_bot_module.Bot = MaxBot

# We'll use the Dispatcher from our fake aiogram (now accessible as aiogram.dispatcher)
from aiogram.dispatcher import Dispatcher

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

dp = Dispatcher()
dp.include_router(echo.router)

MOSCOW_TZ = timezone(timedelta(hours=3))


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
            await bot.send_message(
                admin_id,
                f"✅ Ежедневная индексация диванов завершена. Всего в базе: {count}",
            )
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
    asyncio.create_task(lead_update_worker(bot))


async def on_shutdown(bot: MaxBot) -> None:
    await bot.delete_webhook()
    logger.info("Вебхук удалён")


def max_message_to_aiogram(update_data: dict):
    """
    Convert a Max webhook payload to an aiogram.types.Update object (from our fake aiogram).
    Max payload structure:
    {
        "update_type": "message_created" | "bot_started" | ...,
        "timestamp": ms since epoch,
        "message": {
            "recipient": {"chat_id": int, "chat_type": "dialog"|"group"|"channel"},
            "sender": {"user_id": int, "first_name": str, "last_name": str|None, "username": str|None, "is_bot": bool},
            "body": {"mid": str, "seq": int, "text": str}
        }
    }
    """
    # Import OUR types from the fake aiogram module
    from aiogram.types import Update as AiogramUpdate, Message, User, Chat

    # Debug: Log what we're importing
    logger.debug(f"AiogramUpdate class: {AiogramUpdate}")
    logger.debug(f"AiogramUpdate module: {AiogramUpdate.__module__}")

    update_type = update_data.get("update_type") or update_data.get(
        "type"
    )  # Handle both
    # Max does not send update_id; we can use timestamp as fallback or set 0.
    timestamp = update_data.get("timestamp", 0)
    logger.debug(f"Timestamp from update_data: {timestamp} (type: {type(timestamp)})")
    update_id = int(timestamp) // 1000  # use seconds as pseudo ID
    logger.debug(f"Calculated update_id: {update_id} (type: {type(update_id)})")

    # We only handle message_created updates for now.
    if update_type != "message_created":
        # For other types (bot_started, etc.) we return an Update with no message.
        logger.debug(
            f"Non-message_created update type: {update_type}, returning Update with no message"
        )
        return AiogramUpdate(update_id=update_id, message=None)

    msg = update_data.get("message", {})
    if not msg:
        # If no message in payload, return update with no message
        logger.debug("No message in payload, returning Update with no message")
        return AiogramUpdate(update_id=update_id, message=None)

    # Sender (from_user)
    sender = msg.get("sender", {})
    from_user = User(
        id=sender.get("user_id", 0),
        is_bot=sender.get("is_bot", False),
        first_name=sender.get("first_name"),
        last_name=sender.get("last_name"),
        username=sender.get("username"),
        language_code=None,  # Max does not provide language_code
    )

    # Recipient (chat)
    recipient = msg.get("recipient", {})
    chat_id = recipient.get("chat_id", 0)
    chat_type = recipient.get(
        "chat_type", "private"
    )  # dialog -> private, group -> group, channel -> channel
    # Map Max chat_type to aiogram Chat.type
    # aiogram expects: private, group, supergroup, channel
    if chat_type == "dialog":
        chat_type_ai = "private"
    elif chat_type == "group":
        chat_type_ai = "group"
    elif chat_type == "channel":
        chat_type_ai = "channel"
    else:
        chat_type_ai = "private"

    chat = Chat(
        id=chat_id,
        type=chat_type_ai,
        title=None,  # Max does not provide title in recipient
        username=None,
        first_name=None,
        last_name=None,
    )

    # Message body
    body = msg.get("body", {})
    text = body.get("text", "")
    # Use message id from mid? Not numeric; we can use a hash or timestamp.
    # For simplicity, we can use timestamp as message_id (seconds).
    message_id = int(timestamp) // 1000
    # Date in seconds since epoch
    date = int(timestamp) // 1000

    logger.debug(f"Calculated message_id: {message_id}, date: {date}")
    logger.debug(f"Chat id: {chat_id}, type: {chat_type_ai}")
    logger.debug(f"From user id: {from_user.id}")

    # Build Message
    message = Message(
        message_id=message_id,
        date=date,
        chat=chat,
        from_user=from_user,
        text=text if text else None,
        caption=None,
        contact=None,
        photo=None,
    )

    # Debug: Log the values we're about to use
    logger.debug(
        f"About to create Update with: update_id={update_id}, message={message}"
    )

    # Create and return the Update
    try:
        result = AiogramUpdate(update_id=update_id, message=message)
        logger.debug(f"Successfully created Update: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to create Update object: {e}")
        logger.error(f"update_id value: {update_id} (type: {type(update_id)})")
        logger.error(f"message value: {message}")
        if message:
            logger.error(
                f"message.message_id: {message.message_id} (type: {type(message.message_id)})"
            )
            logger.error(f"message.date: {message.date} (type: {type(message.date)})")
            logger.error(f"message.chat: {message.chat} (type: {type(message.chat)})")
        raise


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
        logger.info(f"Received webhook request: {request.method} {request.path}")
        try:
            update_data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")
        # Convert Max update to aiogram Update (using our fake types)
        try:
            aiogram_update = max_message_to_aiogram(update_data)
            logger.info(f"Converted update: {aiogram_update}")
        except Exception as e:
            logger.error(
                f"Failed to convert Max update: {e}. Update data: {update_data}"
            )
            return web.Response(status=200, text="")  # Return 200 to avoid retries
        # Feed to dp
        try:
            await dp.feed_update(bot, aiogram_update)
        except Exception as e:
            logger.error(f"Error while processing update: {e}")
            # Log the actual update object that caused the error
            logger.error(f"Failing update object: {aiogram_update}")
            if hasattr(aiogram_update, "message") and aiogram_update.message:
                logger.error(f"Failing message: {aiogram_update.message}")
                logger.error(f"Failing message.chat: {aiogram_update.message.chat}")
            return web.Response(status=200, text="")  # Return 200 to avoid retries
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
