# ruff: noqa: E402
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from aiohttp import web

# ──────────────────────────────────────────────────────────────
# 1. Import REAL aiogram + Telegram bot components FIRST
# ──────────────────────────────────────────────────────────────
from aiogram import Bot as TelegramBot
from aiogram.dispatcher.dispatcher import Dispatcher as TelegramDispatcher
from aiogram.types import Update as TelegramUpdate

from bot.config import BOT_TOKEN, HOST, PORT
from bot.database import db as tg_db
from bot.services.ai_service import load_catalog_urls
from bot.routers.echo import router as tg_router

# ──────────────────────────────────────────────────────────────
# 2. Replace aiogram with fake for Max imports
# ──────────────────────────────────────────────────────────────
# Delete ALL real aiogram submodules so the fake one is used
# for any subsequent 'from aiogram import ...' statements.
# The Telegram components already imported have their own
# references to real aiogram classes in their namespaces.
_real_aiogram_modules = {}
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("aiogram"):
        _real_aiogram_modules[mod_name] = sys.modules[mod_name]
        del sys.modules[mod_name]

_fake_dir = os.path.join(os.path.dirname(__file__), "max_bot")
if _fake_dir not in sys.path:
    sys.path.insert(0, _fake_dir)

import fake_aiogram

sys.modules["aiogram"] = fake_aiogram

# ──────────────────────────────────────────────────────────────
# 3. Import Max bot components (use fake aiogram)
# ──────────────────────────────────────────────────────────────
from max_bot.config import MAX_BOT_TOKEN
from max_bot.services.max_client import MaxBot
from max_bot.database import db as max_db
from max_bot.routers.echo import router as max_router
from max_bot.services.ai_service import load_catalog_urls as max_load_catalog_urls
from max_bot.main import max_message_to_aiogram

from aiogram import Dispatcher as FakeDispatcher

# ──────────────────────────────────────────────────────────────
# 4. Create both dispatchers
# ──────────────────────────────────────────────────────────────
tg_dp = TelegramDispatcher()
tg_dp.include_router(tg_router)

max_dp = FakeDispatcher()
max_dp.include_router(max_router)

# ──────────────────────────────────────────────────────────────
# 5. Background workers (copy from both main.py files)
# ──────────────────────────────────────────────────────────────
MOSCOW_TZ = timezone(timedelta(hours=3))
YEKATERINBURG_TZ = timezone(timedelta(hours=5))

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def _is_night_time() -> bool:
    now = datetime.now(YEKATERINBURG_TZ)
    return now.hour >= 23 or now.hour < 9


async def _run_indexing(bot: TelegramBot) -> None:
    try:
        from bot.services.rivalli_parser import run_indexing  # type: ignore[import-untyped]

        logger.info("Запуск ежедневной индексации диванов...")
        sofas = await run_indexing()

        for sofa in sofas:
            await tg_db.save_sofa(
                slug=sofa.slug,
                name=sofa.name,
                url=sofa.url,
                category=sofa.category,
                description=sofa.description,
                features=sofa.features,
                image_urls=",".join(sofa.image_urls) if sofa.image_urls else None,
            )

        count = await tg_db.get_sofa_count()
        logger.info(f"Ежедневная индексация завершена. Всего диванов: {count}")

        admin_id = 1696951195
        try:
            await bot.send_message(admin_id, f"✅ Ежедневная индексация диванов завершена. Всего в базе: {count}")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка ежедневной индексации: {e}")


async def daily_sofa_indexing(bot: TelegramBot) -> None:
    while True:
        now_wall = datetime.now(MOSCOW_TZ)
        target = now_wall.replace(hour=9, minute=0, second=0, microsecond=0)
        if now_wall.hour >= 9:
            target += timedelta(days=1)
        seconds_until = (target - now_wall).total_seconds()
        logger.info(f"Следующая индексация через {seconds_until / 3600:.1f} часов в {target}")
        await asyncio.sleep(seconds_until)
        await _run_indexing(bot)


REMINDER_INTERVALS = ["15min", "3h", "1d"]
REMINDER_CHECK_PERIOD = 60


async def reminder_worker(bot: TelegramBot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            if _is_night_time():
                logger.debug("Ночное время — напоминания отключены")
            else:
                for interval in REMINDER_INTERVALS:
                    pending = await tg_db.get_pending_reminders([interval])
                    for user_id, topic, last_msg in pending:
                        if user_id == 1696951195:
                            continue
                        if last_msg:
                            prompt = f'Клиент не ответил после того как бот отправил:\n"{last_msg[:500]}"\n\nЕсли topic: {topic or "неизвестно"}.\n\nОтправь клиенту мягкое напоминание, 1-2 предложения. Не дави, не продавай агрессивно. Например: «Не нашли то, что искали? Я на связи, если появятся вопросы.»'
                        else:
                            prompt = "Отправь клиенту мягкое напоминание, 1-2 предложения. Не дави, не продавай агрессивно."
                        from bot.services.ai_service import get_ai_service

                        response = await get_ai_service().get_response(prompt, [], user_id)
                        response = response.replace("\\n\\n", "\n\n").replace("\\n", "\n")
                        try:
                            await bot.send_message(user_id, response[:500])
                            await tg_db.mark_reminder_sent(user_id, interval)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Ошибка воркера напоминаний: {e}")
        await asyncio.sleep(REMINDER_CHECK_PERIOD)


LEAD_UPDATE_CHECK_PERIOD = 60


async def lead_update_worker(bot: TelegramBot) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            from datetime import timedelta as dt_timedelta
            from sqlalchemy import select, and_
            from bot.database import ConversationModel

            async with tg_db._session_factory() as session:
                one_minute_ago = datetime.now() - dt_timedelta(minutes=1)
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
                    from bot.config import TELEGRAM_GROUP_ID

                    new_messages = await tg_db.get_messages_after_lead(conv.user_id, conv.lead_sent_at)
                    if new_messages and TELEGRAM_GROUP_ID:
                        text = "🔄 <b>Обновление по заявке</b>\n\n"
                        for msg in new_messages:
                            if msg.user_message and not msg.user_message.startswith("["):
                                text += f"👤 {msg.user_message[:80]}\n"
                            if msg.bot_response and not msg.bot_response.startswith("["):
                                text += f"🤖 {msg.bot_response[:80]}\n"
                        try:
                            await bot.send_message(TELEGRAM_GROUP_ID, text)
                            conv.last_lead_update_at = conv.lead_sent_at
                            await session.commit()
                            logger.info(f"Отправлено обновление по заявке для пользователя {conv.user_id}")
                        except Exception as e:
                            logger.error(f"Не удалось отправить обновление по заявке: {e}")
        except Exception as e:
            logger.error(f"Ошибка воркера обновлений по заявкам: {e}")
        await asyncio.sleep(LEAD_UPDATE_CHECK_PERIOD)


# ──────────────────────────────────────────────────────────────
# 6. Webhook handlers
# ──────────────────────────────────────────────────────────────

async def telegram_webhook_handler(request: web.Request) -> web.Response:
    """Handle incoming Telegram updates."""
    try:
        update_data = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    try:
        update = TelegramUpdate.model_validate(update_data, context={"bot": request.app["tg_bot"]})
    except Exception as e:
        logger.error(f"Failed to parse Telegram update: {e}")
        return web.Response(status=200, text="")

    try:
        await tg_dp.feed_update(bot=request.app["tg_bot"], update=update)
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")
        return web.Response(status=200, text="")

    return web.Response()


async def max_webhook_handler(request: web.Request) -> web.Response:
    """Handle incoming Max updates."""
    try:
        update_data = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    try:
        aiogram_update = max_message_to_aiogram(update_data)
    except Exception as e:
        logger.error(f"Failed to convert Max update: {e}")
        return web.Response(status=200, text="")

    try:
        await max_dp.feed_update(request.app["max_bot"], aiogram_update)
    except Exception as e:
        logger.error(f"Error processing Max update: {e}")
        return web.Response(status=200, text="")

    return web.Response()


# ──────────────────────────────────────────────────────────────
# 7. Startup / Shutdown
# ──────────────────────────────────────────────────────────────

async def on_startup(app: web.Application) -> None:
    tg_bot: TelegramBot = app["tg_bot"]
    max_bot: MaxBot = app["max_bot"]

    # Initialize DB (shared PostgreSQL)
    await tg_db.init_db()
    await max_db.init_db()
    logger.info("База данных инициализирована")

    # Load catalog URLs
    await load_catalog_urls()
    await max_load_catalog_urls()
    logger.info("Каталоги загружены")

    # Register webhooks
    from bot.config import WEBHOOK_URL as TG_BASE_URL, WEBHOOK_PATH as TG_PATH
    from max_bot.config import WEBHOOK_PATH as MAX_PATH

    tg_webhook_url = TG_BASE_URL.rstrip("/") + TG_PATH
    max_webhook_url = TG_BASE_URL.rstrip("/") + MAX_PATH

    await tg_bot.set_webhook(tg_webhook_url)
    logger.info(f"Telegram вебхук установлен на {tg_webhook_url}")

    if MAX_BOT_TOKEN:
        await max_bot.set_webhook(max_webhook_url)
        logger.info(f"Max вебхук установлен на {max_webhook_url}")

    # Start background workers
    asyncio.create_task(daily_sofa_indexing(tg_bot))
    asyncio.create_task(reminder_worker(tg_bot))
    asyncio.create_task(lead_update_worker(tg_bot))


async def on_shutdown(app: web.Application) -> None:
    tg_bot: TelegramBot = app["tg_bot"]
    max_bot: MaxBot = app["max_bot"]

    await tg_bot.delete_webhook()
    logger.info("Telegram вебхук удалён")

    if MAX_BOT_TOKEN:
        await max_bot.delete_webhook()
        logger.info("Max вебхук удалён")

    await tg_bot.session.close()


# ──────────────────────────────────────────────────────────────
# 8. Main
# ──────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("Запуск комбинированного бота (Telegram + Max)...")

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set")

    from bot.config import WEBHOOK_PATH as TG_ROUTE_PATH
    from max_bot.config import WEBHOOK_PATH as MAX_ROUTE_PATH

    tg_bot = TelegramBot(token=BOT_TOKEN, parse_mode="HTML")
    max_bot = MaxBot(token=MAX_BOT_TOKEN) if MAX_BOT_TOKEN else None

    app = web.Application()
    app["tg_bot"] = tg_bot
    app["max_bot"] = max_bot

    app.router.add_post(TG_ROUTE_PATH, telegram_webhook_handler)
    if max_bot:
        app.router.add_post(MAX_ROUTE_PATH, max_webhook_handler)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    logger.info(f"Сервер запущен на http://{HOST}:{PORT}")
    logger.info(f"  Telegram: {TG_ROUTE_PATH}")
    if max_bot:
        logger.info(f"  Max: {MAX_ROUTE_PATH}")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
