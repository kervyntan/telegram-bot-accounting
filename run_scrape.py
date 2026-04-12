"""One-shot script: run scraper pipeline and post listings to Telegram group."""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from telegram import Bot
from telegram.constants import ParseMode

from src.config import load_settings
from src.scraper import ScraperPipeline

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    settings = load_settings()

    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY not set in .env")
    if not settings.scraper_channel_id:
        raise SystemExit("SCRAPER_CHANNEL_ID not set in .env")

    # Use catalogue bot token (it has access to the target group)
    bot_token = os.environ.get("CATALOGUE_BOT_TOKEN")
    if not bot_token:
        raise SystemExit("CATALOGUE_BOT_TOKEN not set in .env")

    bot = Bot(token=bot_token)

    pipeline = ScraperPipeline(
        gemini_api_key=settings.gemini_api_key,
        markup=settings.scraper_markup,
        min_price=settings.scraper_min_price,
        max_price=settings.scraper_max_price,
    )

    logger.info("Running scraper pipeline...")
    listings = await pipeline.run()

    if not listings:
        logger.info("No listings found.")
        return

    logger.info(f"Found {len(listings)} listings. Posting to group...")

    posted = 0
    for listing in listings:
        # Escape markdown special chars in title
        safe_title = listing.english_title.replace("*", "").replace("_", " ").replace("`", "")
        caption = f"*{safe_title}*\nSGD ${listing.final_price}"
        try:
            if listing.processed_image_path:
                with open(listing.processed_image_path, "rb") as photo:
                    await bot.send_photo(
                        chat_id=settings.scraper_channel_id,
                        photo=photo,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                    )
            else:
                await bot.send_message(
                    chat_id=settings.scraper_channel_id,
                    text=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
            posted += 1
        except Exception as e:
            logger.error(f"Failed to post listing: {e}")
        await asyncio.sleep(2)

    logger.info(f"Done! Posted {posted}/{len(listings)} listings.")

    # Print summary
    for listing in listings:
        print(
            f"  {listing.english_title} | "
            f"¥{listing.raw_price_jpy:,} → SGD ${listing.final_price} | "
            f"{listing.source_url}"
        )


if __name__ == "__main__":
    asyncio.run(main())
