"""Vercel serverless function — Telegram webhooks for invoice + catalogue bots.

Both /api/webhook (invoice bot) and /api/catalogue_webhook (catalogue bot)
are handled here so Vercel runs a single Python function file.
"""

import asyncio
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Ensure `src` package is importable on Vercel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Update  # noqa: E402

from src.bot import InvoiceBot  # noqa: E402
from src.catalogue_bot import CatalogueBot  # noqa: E402
from src.config import load_catalogue_settings, load_settings  # noqa: E402

logger = logging.getLogger(__name__)


async def _run_scheduled_scrape() -> str:
    """Run the scraper pipeline and post new listings to the channel."""
    settings = load_settings()

    required = (settings.gemini_api_key, settings.scraper_channel_id, settings.catalogue_bot_token)
    if not all(required):
        return "Skipped: missing config"

    bot = InvoiceBot(settings)
    posted, total, _ = await bot._run_scrape_and_post()

    # Notify admin
    if settings.telegram_chat_id and total > 0:
        from telegram import Bot

        admin_bot = Bot(token=settings.telegram_bot_token)
        await admin_bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=f"🔄 Daily scrape: posted {posted}/{total} new Pokémon promo listings.",
        )

    return f"Posted {posted}/{total} new listings"


async def _handle_invoice_update(payload: dict) -> None:
    """Process one invoice-bot update with a fresh Application lifecycle."""
    settings = load_settings()
    bot = InvoiceBot(settings)
    async with bot.app:
        update = Update.de_json(payload, bot.app.bot)
        await bot.app.process_update(update)


async def _handle_catalogue_update(payload: dict) -> None:
    """Process one catalogue-bot update with a fresh Application lifecycle."""
    settings = load_catalogue_settings()
    bot = CatalogueBot(settings)
    async with bot.app:
        update = Update.de_json(payload, bot.app.bot)
        await bot.app.process_update(update)


class handler(BaseHTTPRequestHandler):
    """Single Vercel handler that serves both bot webhooks."""

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        path = self.path.split("?")[0]
        try:
            if path == "/api/catalogue_webhook":
                asyncio.run(_handle_catalogue_update(payload))
            else:
                asyncio.run(_handle_invoice_update(payload))
        except Exception:
            logger.exception("Error processing update for path %s", path)

        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Health check and cron endpoints."""
        path = self.path.split("?")[0]

        if path == "/api/cron/scrape":
            try:
                result = asyncio.run(_run_scheduled_scrape())
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "result": result}).encode())
            except Exception as e:
                logger.exception("Cron scrape failed")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "error": str(e)}).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if path == "/api/catalogue_webhook":
            self.wfile.write(b'{"status":"ok","bot":"catalogue"}')
        else:
            self.wfile.write(b'{"status":"ok","bot":"invoice"}')
