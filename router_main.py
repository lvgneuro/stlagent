# ruff: noqa: E402
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
BASE_URL = (
    os.getenv("WEBHOOK_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or "https://stlagent-5qrr.onrender.com"
)
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
TG_WEBHOOK_PATH = os.getenv("TG_WEBHOOK_PATH", "/tg-webhook")
MAX_WEBHOOK_PATH = os.getenv("MAX_WEBHOOK_PATH", "/max-webhook")

MOSCOW_TZ = timezone(timedelta(hours=3))
YEKATERINBURG_TZ = timezone(timedelta(hours=5))


# ── Telegram Bot Setup ───────────────────────────────────────
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.types import Update

tg_bot = (
    Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if BOT_TOKEN
    else None
)
tg_dp = Dispatcher()

from bot.database import db as tg_db
from bot.services.ai_service import load_catalog_urls
from bot.routers.echo import router as tg_router

tg_dp.include_router(tg_router)


# ── Max Bot Setup ─────────────────────────────────────────────
max_bot = None
max_dp = None


# ── Handlers ──────────────────────────────────────────────────


async def telegram_webhook_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": tg_bot})
        await tg_dp.feed_update(bot=tg_bot, update=update)
    except Exception as e:
        logger.error(f"TG webhook error: {e}")
    return web.Response()


async def max_webhook_handler(request: web.Request) -> web.Response:
    """Convert Max payload → fake Update → feed to same dispatcher with max_bot."""
    try:
        data = await request.json()
        update_type = data.get("update_type") or data.get("type")
        timestamp = data.get("timestamp", 0)
        update_id = int(timestamp) // 1000

        if update_type != "message_created":
            return web.Response()

        msg = data.get("message", {})
        sender = msg.get("sender", {})
        recipient = msg.get("recipient", {})
        body = msg.get("body", {})
        text = body.get("text", "")

        # Build a minimal Update manually (no real aiogram validation)
        # We construct a dict in the shape aiogram expects
        fake_update = {
            "update_id": update_id,
            "message": {
                "message_id": update_id,
                "date": update_id,
                "from": {
                    "id": sender.get("user_id", 0),
                    "is_bot": sender.get("is_bot", False),
                    "first_name": sender.get("first_name", "User"),
                    "last_name": sender.get("last_name"),
                    "username": sender.get("username"),
                    "language_code": None,
                },
                "chat": {
                    "id": recipient.get("chat_id", 0),
                    "type": "private"
                    if recipient.get("chat_type", "dialog") == "dialog"
                    else recipient.get("chat_type", "private"),
                    "first_name": sender.get("first_name"),
                    "last_name": sender.get("last_name"),
                    "username": sender.get("username"),
                },
                "text": text,
            },
        }

        update = Update.model_validate(fake_update, context={"bot": max_bot})
        await tg_dp.feed_update(bot=max_bot, update=update)
    except Exception as e:
        logger.error(f"Max webhook error: {e}", exc_info=True)
    return web.Response()


async def old_webhook_fallback(request: web.Request) -> web.Response:
    return web.Response()


# ── Startup / Shutdown ───────────────────────────────────────


async def on_startup(app: web.Application) -> None:
    await tg_db.init_db()
    logger.info("База данных инициализирована")

    await load_catalog_urls()

    tg_url = BASE_URL.rstrip("/") + TG_WEBHOOK_PATH
    await tg_bot.set_webhook(tg_url)
    logger.info(f"Telegram вебхук: {tg_url}")

    if max_bot:
        max_url = BASE_URL.rstrip("/") + MAX_WEBHOOK_PATH
        await max_bot.set_webhook(max_url)
        logger.info(f"Max вебхук: {max_url}")

    from bot.database import db

    count = await db.get_sofa_count()
    logger.info(f"Диванов в БД: {count}")

    asyncio.create_task(_daily_indexing(tg_bot))
    asyncio.create_task(_reminder_worker(tg_bot))
    asyncio.create_task(_lead_worker(tg_bot))


async def on_shutdown(app: web.Application) -> None:
    await tg_bot.delete_webhook()
    if max_bot:
        await max_bot.delete_webhook()
    # Don't close session if max_bot doesn't have it
    if hasattr(tg_bot, "session"):
        await tg_bot.session.close()


# ── Workers ───────────────────────────────────────────────────


def _is_night() -> bool:
    now = datetime.now(YEKATERINBURG_TZ)
    return now.hour >= 23 or now.hour < 9


async def _daily_indexing(bot: Bot) -> None:
    while True:
        now = datetime.now(MOSCOW_TZ)
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now.hour >= 9:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

        try:
            from bot.services.rivalli_parser import run_indexing
            from bot.database import db

            sofas = await run_indexing()
            for s in sofas:
                await db.save_sofa(
                    slug=s.slug,
                    name=s.name,
                    url=s.url,
                    category=s.category,
                    description=s.description,
                    features=s.features,
                    image_urls=",".join(s.image_urls) if s.image_urls else None,
                )
            c = await db.get_sofa_count()
            logger.info(f"Индексация завершена: {c} диванов")
            try:
                await bot.send_message(1696951195, f"✅ Индексация: {c} диванов")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Ошибка индексации: {e}")


async def _reminder_worker(bot: Bot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            if not _is_night():
                from bot.database import db
                from bot.services.ai_service import get_ai_service

                for interval in ("15min", "3h", "1d"):
                    for uid, topic, last in await db.get_pending_reminders([interval]):
                        if uid == 1696951195:
                            continue
                        prompt = (
                            f'Клиент не ответил после: "{last[:500]}"\n\nОтправь мягкое напоминание 1-2 предложения.'
                            if last
                            else "Отправь мягкое напоминание."
                        )
                        resp = await get_ai_service().get_response(prompt, [], uid)
                        resp = resp.replace("\\n\\n", "\n\n").replace("\\n", "\n")
                        try:
                            await bot.send_message(uid, resp[:500])
                            await db.mark_reminder_sent(uid, interval)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Reminder error: {e}")
        await asyncio.sleep(60)


async def _lead_worker(bot: Bot) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            from datetime import timedelta as dt_td
            from sqlalchemy import select, and_
            from bot.database import ConversationModel, db

            async with db._session_factory() as session:
                cutoff = datetime.now() - dt_td(minutes=1)
                rows = await session.execute(
                    select(ConversationModel).where(
                        and_(
                            ConversationModel.lead_sent_at.isnot(None),
                            ConversationModel.last_lead_update_at.is_(None),
                            ConversationModel.lead_sent_at < cutoff,
                        )
                    )
                )
                for conv in rows.scalars().all():
                    if conv.user_id == 1696951195:
                        continue
                    msgs = await db.get_messages_after_lead(
                        conv.user_id, conv.lead_sent_at
                    )
                    if msgs and TELEGRAM_GROUP_ID:
                        lines = []
                        for m in msgs:
                            if m.user_message and not m.user_message.startswith("["):
                                lines.append(f"👤 {m.user_message[:80]}")
                            if m.bot_response and not m.bot_response.startswith("["):
                                lines.append(f"🤖 {m.bot_response[:80]}")
                        if lines:
                            text = "🔄 <b>Обновление по заявке</b>\n\n" + "\n".join(
                                lines
                            )
                            await bot.send_message(int(TELEGRAM_GROUP_ID), text)
                            conv.last_lead_update_at = conv.lead_sent_at
                            await session.commit()
        except Exception as e:
            logger.error(f"Lead worker error: {e}")
        await asyncio.sleep(60)


# ── Main ──────────────────────────────────────────────────────


async def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set")

    logger.info("Запуск комбинированного бота (Telegram + Max)...")

    app = web.Application()
    app["tg_bot"] = tg_bot
    app["max_bot"] = max_bot

    app.router.add_post(TG_WEBHOOK_PATH, telegram_webhook_handler)
    if max_bot:
        app.router.add_post(MAX_WEBHOOK_PATH, max_webhook_handler)
    app.router.add_post("/webhook", old_webhook_fallback)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    logger.info(f"Сервер: http://{HOST}:{PORT}")
    logger.info(f"  Telegram: {TG_WEBHOOK_PATH}")
    if max_bot:
        logger.info(f"  Max: {MAX_WEBHOOK_PATH}")
    logger.info("  Legacy /webhook: 200 OK")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
