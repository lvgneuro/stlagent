from __future__ import annotations

import asyncio
import logging
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from bot.config import (
    BOT_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_PATH,
    HOST,
    PORT,
)
from bot.routers import echo
from bot.database import db

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

logger = logging.getLogger(__name__)

dp = Dispatcher()
dp.include_router(echo.router)


async def daily_sofa_indexing(bot: Bot) -> None:
    while True:
        try:
            from bot.services.rivalli_parser import run_indexing

            logger.info("Starting daily sofa indexing...")
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
            logger.info(f"Daily indexing completed. Total sofas: {count}")

            admin_id = 1696951195
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ Ежедневная индексация диванов завершена. Всего в базе: {count}",
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Daily indexing error: {e}")

        await asyncio.sleep(86400)


async def on_startup(bot: Bot) -> None:
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    sofa_count = await db.get_sofa_count()
    logger.info(f"Sofa count in DB: {sofa_count}")
    if sofa_count == 0:
        logger.info("No sofas in database, starting initial indexing...")
        try:
            from bot.services.rivalli_parser import run_indexing
            sofas = await run_indexing()
            logger.info(f"Indexed {len(sofas)} sofas from parser")
            saved_count = 0
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
                saved_count += 1
            final_count = await db.get_sofa_count()
            logger.info(f"Initial indexing completed. Saved: {saved_count}, Total in DB: {final_count}")
        except Exception as e:
            logger.error(f"Initial indexing failed: {e}")

    asyncio.create_task(daily_sofa_indexing(bot))


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    logger.info("Webhook deleted")


async def main() -> None:
    logger.info("Starting bot in webhook mode...")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set")

    await db.init_db()
    logger.info("Database initialized")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await on_startup(bot)

    app = web.Application()
    app["bot"] = bot

    webhook_request_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_request_handler.register(app, path=WEBHOOK_PATH)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    logger.info(f"Webhook server started on http://{HOST}:{PORT}{WEBHOOK_PATH}")

    try:
        await asyncio.Event().wait()
    finally:
        await on_shutdown(bot)
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
