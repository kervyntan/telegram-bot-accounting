"""Vercel serverless function — Telegram webhook for the catalogue search bot."""

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Ensure `src` package is importable on Vercel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.catalogue_bot import CatalogueBot  # noqa: E402
from src.config import load_catalogue_settings  # noqa: E402

logger = logging.getLogger(__name__)

# Module-level singleton — reused across warm invocations.
_bot: CatalogueBot | None = None
_initialized = False


async def _get_bot() -> CatalogueBot:
    """Lazy-init the catalogue bot singleton and register the webhook once."""
    global _bot, _initialized
    if _bot is None:
        settings = load_catalogue_settings()
        _bot = CatalogueBot(settings)
    if not _initialized:
        await _bot.setup_webhook()
        _initialized = True
    return _bot


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for POST /api/catalogue_webhook."""

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._process(payload))
        except Exception:
            logger.exception("Error processing catalogue update")

        self.send_response(200)
        self.end_headers()

    async def _process(self, payload: dict) -> None:
        bot = await _get_bot()
        await bot.process_update(payload)

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","bot":"catalogue"}')
