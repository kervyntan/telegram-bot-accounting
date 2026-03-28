"""Orchestrator: ties Phases 1-3 together into a single async pipeline."""

import hashlib
import logging
from dataclasses import dataclass

from .image_processor import process_listing_image
from .marketplace import (
    SEARCH_KEYWORDS,
    RawListing,
    fetch_exchange_rate,
    scrape_doorzo,
)
from .pricing import calculate_price
from .translator import translate_titles_batch

logger = logging.getLogger(__name__)


@dataclass
class ProcessedListing:
    """A fully processed listing ready for Telegram posting."""

    english_title: str
    final_price: int  # SGD, whole number
    processed_image_path: str | None
    source_url: str  # admin-only tracking
    raw_price_jpy: int
    category: str  # "ar_chr_rr" or "sar_csr_sr"


class ScraperPipeline:
    """End-to-end pipeline: scrape → translate → price."""

    def __init__(
        self,
        gemini_api_key: str,
        target_currency: str = "SGD",
        markup: float = 1.3,
        min_price: float = 1.0,
        max_price: float = 200.0,
        gemini_model: str = "gemini-2.5-flash",
    ):
        self.gemini_api_key = gemini_api_key
        self.target_currency = target_currency
        self.markup = markup
        self.min_price = min_price
        self.max_price = max_price
        self.gemini_model = gemini_model

    async def run(
        self,
        categories: list[str] | None = None,
        custom_keywords: dict[str, list[str]] | None = None,
    ) -> list[ProcessedListing]:
        """Execute the full pipeline."""
        keywords_map = custom_keywords or SEARCH_KEYWORDS
        if categories:
            keywords_map = {k: v for k, v in keywords_map.items() if k in categories}

        # Phase 1: Get exchange rate and scrape
        logger.info("Phase 1: Fetching exchange rate and scraping marketplaces...")
        jpy_rate = await fetch_exchange_rate(self.target_currency)

        all_raw: list[RawListing] = []
        for category, keywords in keywords_map.items():
            raw = await scrape_doorzo(
                keywords=keywords,
                category=category,
                jpy_to_sgd_rate=jpy_rate,
                min_price_sgd=self.min_price,
                max_price_sgd=self.max_price,
            )
            all_raw.extend(raw)

        logger.info(f"Phase 1 complete: {len(all_raw)} listings scraped")

        if not all_raw:
            return []

        # Phase 2: Batch translate all titles in a single API call
        logger.info("Phase 2: Batch translating titles...")
        raw_titles = [listing.raw_title for listing in all_raw]
        translated_titles = await translate_titles_batch(
            raw_titles,
            api_key=self.gemini_api_key,
            model=self.gemini_model,
        )

        # Phase 3: Process images and calculate prices
        results: list[ProcessedListing] = []
        for i, listing in enumerate(all_raw):
            listing_id = hashlib.md5(
                f"{listing.source_url}{listing.raw_title}".encode()
            ).hexdigest()[:12]

            logger.info(f"Processing listing {i + 1}/{len(all_raw)}: {translated_titles[i][:60]}...")

            image_path = await process_listing_image(listing.image_url, listing_id)

            final_price = calculate_price(
                listing.raw_price_jpy,
                jpy_rate,
                self.markup,
            )

            results.append(
                ProcessedListing(
                    english_title=translated_titles[i],
                    final_price=final_price,
                    processed_image_path=image_path,
                    source_url=listing.source_url,
                    raw_price_jpy=listing.raw_price_jpy,
                    category=listing.category,
                )
            )

        logger.info(f"Pipeline complete: {len(results)} listings processed")
        return results
