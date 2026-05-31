from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from bot.config import (
    BOT_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_PATH,
    HOST,
    PORT,
    TELEGRAM_GROUP_ID,
)
from bot.routers import echo
from bot.database import db
from bot.services.ai_service import get_ai_service

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

logger = logging.getLogger(__name__)

dp = Dispatcher()
dp.include_router(echo.router)

MOSCOW_TZ = timezone(timedelta(hours=3))
YEKATERINBURG_TZ = timezone(timedelta(hours=5))


def _is_night_time() -> bool:
    now = datetime.now(YEKATERINBURG_TZ)
    return now.hour >= 23 or now.hour < 9


async def _run_indexing(bot: Bot) -> None:
    try:
        from bot.services.rivalli_parser import run_indexing

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

        admin_id = 1696951195
        try:
            await bot.send_message(
                admin_id,
                f"✅ Ежедневная индексация диванов завершена. Всего в базе: {count}",
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Ошибка ежедневной индексации: {e}")


async def daily_sofa_indexing(bot: Bot) -> None:
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


REMINDER_CHECK_PERIOD = 3600


async def reminder_worker(bot: Bot) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            if _is_night_time():
                logger.debug("Ночное время — напоминания отключены")
            else:
                pending = await db.get_pending_reminders()
                for user_id, topic, last_msg, intervals in pending:
                    if user_id == 1696951195:
                        continue
                    labels = {
                        "15min": "15 минут",
                        "3h": "3 часа",
                        "1d": "1 день",
                    }
                    names = [labels[i] for i in intervals]
                    if last_msg:
                        prompt = f'Клиент не ответил после того как бот отправил:\n"{last_msg[:500]}"\n\nТема: {topic or "неизвестно"}.\nПрошло: {", ".join(names)}.\n\nОтправь клиенту мягкое напоминание, 1-2 предложения. Не дави, не продавай агрессивно. Например: «Не нашли то, что искали? Я на связи, если появятся вопросы.»'
                    else:
                        prompt = "Отправь клиенту мягкое напоминание, 1-2 предложения. Не дави, не продавай агрессивно."

                    response = await get_ai_service().get_response(
                        prompt, [], user_id, skip_search=True
                    )
                    response = response.replace("\\n\\n", "\n\n").replace(
                        "\\n", "\n"
                    )
                    try:
                        await bot.send_message(user_id, response[:500])
                        for interval in intervals:
                            await db.mark_reminder_sent(user_id, interval)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Ошибка воркера напоминаний: {e}")
        await asyncio.sleep(REMINDER_CHECK_PERIOD)


LEAD_UPDATE_CHECK_PERIOD = 60


async def lead_update_worker(bot: Bot) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            from datetime import timedelta

            from sqlalchemy import select, and_

            async with db._session_factory() as session:
                from bot.database import ConversationModel

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


async def on_startup(bot: Bot) -> None:
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Telegram вебхук: {WEBHOOK_URL}")

    sofa_count = await db.get_sofa_count()
    logger.info(f"Количество диванов в БД: {sofa_count}")

    asyncio.create_task(daily_sofa_indexing(bot))
    asyncio.create_task(reminder_worker(bot))
    asyncio.create_task(lead_update_worker(bot))


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    logger.info("Вебхук Telegram удалён")


def _resolve_base_url() -> str:
    """Get the base URL (scheme + host) without path."""
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        return render_url.rstrip("/")
    base = WEBHOOK_URL or "https://stlagent-5qrr.onrender.com"
    parsed = urlparse(base)
    return f"{parsed.scheme}://{parsed.netloc}"


async def webhook_handler(request: web.Request) -> web.Response:
    """Handle POST /webhook — Telegram updates only."""
    try:
        body = await request.text()
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return web.Response(status=200, text="OK")

    if "update_id" not in data:
        return web.Response(status=200, text="OK")

    try:
        update = Update.model_validate(data)
        bot = request.app.get("bot")
        if bot:
            await request.app["dp"].feed_update(bot=bot, update=update)
    except Exception as e:
        logger.warning(f"Ошибка обработки Telegram update: {e}")
    return web.Response(status=200, text="OK")


async def max_webhook_handler(request: web.Request) -> web.Response:
    """Handle POST /max-webhook — Max platform messages."""
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=200, text="OK")

    max_bot = request.app.get("max_bot")
    if max_bot:
        await _process_max_update(request.app["dp"], max_bot, data)
    return web.Response(status=200, text="OK")


async def _process_max_update(dp: Dispatcher, max_bot, data: dict) -> None:
    """Convert Max payload and feed to dispatcher."""
    from bot.services.converter import max_to_telegram_dict

    # Debug: log the raw webhook payload
    import json
    logger.info(f"Max webhook payload: {json.dumps(data, ensure_ascii=False)[:500]}")

    try:
        update_dict = max_to_telegram_dict(data)
        update = Update.model_validate(update_dict)
        await dp.feed_update(bot=max_bot, update=update)
    except Exception as e:
        logger.exception(f"Ошибка обработки Max update: {e}")


async def main() -> None:
    logger.info("Запуск бота в режиме вебхука...")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set")

    await db.init_db()
    logger.info("База данных инициализирована")

    from bot.services.ai_service import load_catalog_urls

    await load_catalog_urls()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp

    # Max bot (optional)
    MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
    MAX_WEBHOOK_PATH = os.getenv("MAX_WEBHOOK_PATH", "/max-webhook")
    max_bot = None
    if MAX_BOT_TOKEN:
        from bot.services.max_client import MaxBot

        max_bot = MaxBot(token=MAX_BOT_TOKEN)
        app["max_bot"] = max_bot
        logger.info("Max bot инициализирован")

    # Register routes
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    if max_bot:
        app.router.add_post(MAX_WEBHOOK_PATH, max_webhook_handler)

    # Register Telegram webhook
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Telegram вебхук: {WEBHOOK_URL}")

    # Register Max webhook
    if max_bot:
        base_url = _resolve_base_url()
        max_full_url = base_url + MAX_WEBHOOK_PATH
        try:
            await max_bot.set_webhook(max_full_url)
            logger.info(f"Max вебхук: {max_full_url}")
        except Exception as e:
            logger.exception(f"Не удалось зарегистрировать Max вебхук: {e}")

    # Start background tasks
    sofa_count = await db.get_sofa_count()
    logger.info(f"Количество диванов в БД: {sofa_count}")

    asyncio.create_task(daily_sofa_indexing(bot))
    asyncio.create_task(reminder_worker(bot))
    asyncio.create_task(lead_update_worker(bot))

    # Start HTTP server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    logger.info(f"Вебхук-сервер запущен на http://{HOST}:{PORT}")
    logger.info(f"  Telegram: {WEBHOOK_PATH}")
    if max_bot:
        logger.info(f"  Max: {MAX_WEBHOOK_PATH}")

    try:
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook()
        logger.info("Вебхук Telegram удалён")
        if max_bot:
            try:
                await max_bot.delete_webhook()
            except Exception:
                pass
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
