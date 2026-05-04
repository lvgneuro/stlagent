from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret_token")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    print(f"DEBUG: BOT_TOKEN env var = '{BOT_TOKEN}'", file=sys.stderr)
    print(f"DEBUG: All env vars with TOKEN: {[k for k in os.environ.keys() if 'TOKEN' in k]}", file=sys.stderr)
    raise ValueError("BOT_TOKEN not found in .env file")

logger = logging.getLogger(__name__)