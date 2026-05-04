from __future__ import annotations

import asyncio
import logging
import sys
import hashlib
import hmac
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.types import Update

from bot.config import (
    BOT_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    HOST,
    PORT,
)
from bot.routers import echo

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

logger = logging.getLogger(__name__)

dp = Dispatcher()
dp.include_router(echo.router)


def verify_signature(body: bytes, secret: str, signature: str) -> bool:
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def on_startup(bot: Bot) -> None:
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set in .env")
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    logger.info("Webhook deleted")


async def main() -> None:
    logger.info("Starting bot in webhook mode...")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL is not set. Use ngrok or other HTTPS endpoint.")

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