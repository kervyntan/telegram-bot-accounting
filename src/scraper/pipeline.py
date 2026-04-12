"""Orchestrator: ties Phases 1-3 together into a single async pipeline."""

import logging
from dataclasses import dataclass

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

    listing_id: str  # Doorzo Asin — used for de-duplication
    english_title: str
    final_price: int  # SGD, whole number
    image_url: str  # Full-res image URL (sent directly to Telegram)
    source_url: str  # admin-only tracking
    raw_price_jpy: int
    category: str


class ScraperPipeline:
    """End-to-end pipeline: scrape → de-duplicate → translate → price."""

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
        seen_listing_ids: set[str] | None = None,
    ) -> list[ProcessedListing]:
        """Execute the full pipeline.

        Args:
            categories: Optional list of category keys to scrape.
            custom_keywords: Override default SEARCH_KEYWORDS.
            seen_listing_ids: Set of listing IDs already sent — these will be
                skipped to avoid duplicates.
        """
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

        # De-duplicate against previously sent listings
        if seen_listing_ids:
            before = len(all_raw)
            all_raw = [r for r in all_raw if r.listing_id not in seen_listing_ids]
            skipped = before - len(all_raw)
            if skipped:
                logger.info(f"De-duplicated: skipped {skipped} already-sent listings")

        if not all_raw:
            logger.info("No new listings after de-duplication")
            return []

        # Phase 2: Batch translate all titles in a single API call
        logger.info("Phase 2: Batch translating titles...")
        raw_titles = [listing.raw_title for listing in all_raw]
        translated_titles = await translate_titles_batch(
            raw_titles,
            api_key=self.gemini_api_key,
            model=self.gemini_model,
        )

        # Phase 3: Calculate prices (images are passed through as URLs)
        results: list[ProcessedListing] = []
        for i, listing in enumerate(all_raw):
            logger.info(
                f"Processing listing {i + 1}/{len(all_raw)}: {translated_titles[i][:60]}..."
            )

            final_price = calculate_price(
                listing.raw_price_jpy,
                jpy_rate,
                self.markup,
            )

            results.append(
                ProcessedListing(
                    listing_id=listing.listing_id,
                    english_title=translated_titles[i],
                    final_price=final_price,
                    image_url=listing.image_url,
                    source_url=listing.source_url,
                    raw_price_jpy=listing.raw_price_jpy,
                    category=listing.category,
                )
            )

        logger.info(f"Pipeline complete: {len(results)} listings processed")
        return results
