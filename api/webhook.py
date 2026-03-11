"""Vercel serverless function — Telegram webhook for the invoice bot."""

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
from src.config import load_settings  # noqa: E402

logger = logging.getLogger(__name__)


async def _handle_update(payload: dict) -> None:
    """Process a single Telegram update using a fresh Application lifecycle."""
    settings = load_settings()
    invoice_bot = InvoiceBot(settings)
    async with invoice_bot.app:
        update = Update.de_json(payload, invoice_bot.app.bot)
        await invoice_bot.app.process_update(update)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for POST /api/webhook."""

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        try:
            asyncio.run(_handle_update(payload))
        except Exception:
            logger.exception("Error processing update")

        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
