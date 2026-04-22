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
    """Run the scraper pipeline and post only new listings to the channel."""
    from telegram import Bot
    from telegram.constants import ParseMode

    from src.scraper import ScraperPipeline

    settings = load_settings()

    required = (settings.gemini_api_key, settings.scraper_channel_id, settings.catalogue_bot_token)
    if not all(required):
        return "Skipped: missing config"

    # De-duplication via MongoDB
    scraper_storage = None
    seen_ids: set[str] = set()
    if settings.mongodb_uri:
        from src.mongo_storage import ScraperListingStorage

        scraper_storage = ScraperListingStorage(settings.mongodb_uri, settings.mongodb_database)
        seen_ids = scraper_storage.get_seen_ids()

    pipeline = ScraperPipeline(
        gemini_api_key=settings.gemini_api_key,
        markup=settings.scraper_markup,
        min_price=settings.scraper_min_price,
        max_price=settings.scraper_max_price,
    )
    listings = await pipeline.run(seen_listing_ids=seen_ids)

    if not listings:
        if scraper_storage:
            scraper_storage.close()
        return "No new listings"

    catalogue_bot = Bot(token=settings.catalogue_bot_token)
    topic_id = settings.scraper_topic_pokemon_promo

    posted = 0
    for listing in listings:
        caption = f"*{listing.english_title}*\nSGD ${listing.final_price}"
        for attempt in range(3):
            try:
                await catalogue_bot.send_photo(
                    chat_id=settings.scraper_channel_id,
                    message_thread_id=topic_id,
                    photo=listing.image_url,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
                if scraper_storage:
                    scraper_storage.mark_sent(
                        listing.listing_id, listing.english_title, listing.source_url
                    )
                posted += 1
                break
            except Exception as e:
                if ("Flood control" in str(e) or "429" in str(e)) and attempt < 2:
                    await asyncio.sleep(25)
                    continue
                logger.error(f"Failed to post listing: {e}")
                break
        await asyncio.sleep(1.5)

    if scraper_storage:
        scraper_storage.close()

    # Notify admin
    if settings.telegram_chat_id and posted > 0:
        admin_bot = Bot(token=settings.telegram_bot_token)
        await admin_bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=f"🔄 Daily scrape: posted {posted}/{len(listings)} new listings.",
        )

    return f"Posted {posted}/{len(listings)} new listings"


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
