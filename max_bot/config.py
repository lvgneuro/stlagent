from __future__ import annotations

import logging
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

MAX_TOKEN = os.getenv("MAX_TOKEN")
WEBHOOK_URL = (
    os.getenv("WEBHOOK_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or "https://stlagent-5qrr.onrender.com"
)
WEBHOOK_PATH = os.getenv("MAX_WEBHOOK_PATH", "/max-webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret_token")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

if not MAX_TOKEN:
    print(f"DEBUG: MAX_TOKEN env var = '{MAX_TOKEN}'", file=sys.stderr)
    print(
        f"DEBUG: All env vars with TOKEN: {[k for k in os.environ.keys() if 'TOKEN' in k]}",
        file=sys.stderr,
    )
    raise ValueError("MAX_TOKEN not found in .env file")
