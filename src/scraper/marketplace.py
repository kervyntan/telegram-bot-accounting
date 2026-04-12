"""Phase 1: Scrape trading card listings from Japanese marketplaces via Doorzo API."""

import asyncio
import logging
import random
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Search keywords for different card categories
SEARCH_KEYWORDS = {
    "pokemon_promo": ["pikachu promo"],
}

DOORZO_API_URL = "https://sig.doorzo.com/"
DOORZO_DEFAULT_HEADERS = {
    "accept": "*/*",
    "origin": "https://www.doorzo.com",
    "referer": "https://www.doorzo.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "timezone": "Asia/Singapore",
}


@dataclass
class RawListing:
    """A scraped listing from a Japanese marketplace."""

    listing_id: str  # Doorzo Asin — unique identifier for de-duplication
    raw_title: str
    raw_price_jpy: int
    image_url: str
    source_url: str
    category: str


async def fetch_exchange_rate(target_currency: str = "SGD") -> float:
    """Fetch live JPY → target currency exchange rate.

    Returns the rate as: 1 JPY = X target_currency.
    """
    url = "https://open.er-api.com/v6/latest/JPY"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            rate = data["rates"].get(target_currency)
            if rate is None:
                raise ValueError(f"Currency {target_currency} not found in exchange rate data")
            logger.info(f"Exchange rate: 1 JPY = {rate} {target_currency}")
            return rate
    except Exception as e:
        logger.error(f"Failed to fetch exchange rate: {e}")
        raise


def _decode_hex_url(hex_str: str) -> str:
    """Decode a hex-encoded URL from the Doorzo API."""
    try:
        return bytes.fromhex(hex_str).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""


def _to_full_res_image_url(thumb_url: str) -> str:
    """Convert a Mercari thumbnail URL to a full-resolution image URL.

    Thumbnail: https://static.mercdn.net/thumb/item/webp/m..._1.jpg?ts
    Full-res:  https://static.mercdn.net/photos/m..._1.jpg?ts
    """
    # Extract the filename (e.g. m26439779487_1.jpg?1774680309)
    # from /thumb/item/webp/<filename>
    if "/thumb/item/webp/" in thumb_url:
        filename = thumb_url.split("/thumb/item/webp/")[-1]
        return f"https://static.mercdn.net/photos/{filename}"
    return thumb_url


async def _doorzo_search_page(
    client: httpx.AsyncClient,
    keyword: str,
    next_page_token: str = "",
    website: str = "mercari",
) -> dict:
    """Fetch a single page of Doorzo search results."""
    params = {
        "n": "Sig.Front.SubSite.AppGlobal.MixSearch",
        "from": "INTERNATIONAL",
        "isNew": "15",
        "language": "en",
        "keyword": keyword,
        "filter": "",
        "classification": "",
        "website": website,
        "category": "",
        "condition": "",
        "seller": "",
        "onlyInStock": "1",
        "nextPageToken": next_page_token,
        "deviceId": "pc_bot_scraper",
    }
    resp = await client.get(
        DOORZO_API_URL,
        params=params,
        headers=DOORZO_DEFAULT_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


async def scrape_doorzo(
    keywords: list[str],
    category: str,
    jpy_to_sgd_rate: float,
    min_price_sgd: float = 1.0,
    max_price_sgd: float = 200.0,
    max_results_per_keyword: int = 60,
    max_pages_per_keyword: int = 5,
) -> list[RawListing]:
    """Search Doorzo API for listings matching keywords.

    Paginates through results using nextPageToken. Filters by SGD price range.
    """
    listings: list[RawListing] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient() as client:
        for keyword in keywords:
            count = 0
            next_token = ""

            for page_num in range(max_pages_per_keyword):
                try:
                    logger.info(f"Doorzo search: keyword='{keyword}' page={page_num + 1}")
                    data = await _doorzo_search_page(client, keyword, next_page_token=next_token)

                    if data.get("code") != 200:
                        logger.warning(f"Doorzo API error: {data.get('msg', 'unknown')}")
                        break

                    items = data.get("data", {}).get("items", [])
                    if not items:
                        break

                    for item in items:
                        if count >= max_results_per_keyword:
                            break

                        asin = item.get("Asin", "")
                        if asin in seen_ids:
                            continue
                        seen_ids.add(asin)

                        raw_title = item.get("Name", "")
                        raw_price_jpy = item.get("JPYPrice", 0)
                        image_url = _to_full_res_image_url(item.get("ImageUrl", ""))
                        source_url = _decode_hex_url(item.get("Url", ""))

                        if not (raw_title and raw_price_jpy and image_url and source_url):
                            continue

                        # Filter by converted price range
                        price_sgd = raw_price_jpy * jpy_to_sgd_rate
                        if price_sgd < min_price_sgd or price_sgd > max_price_sgd:
                            continue

                        listings.append(
                            RawListing(
                                listing_id=asin,
                                raw_title=raw_title,
                                raw_price_jpy=raw_price_jpy,
                                image_url=image_url,
                                source_url=source_url,
                                category=category,
                            )
                        )
                        count += 1

                    if count >= max_results_per_keyword:
                        break

                    # Get next page token
                    next_token = data.get("data", {}).get("nextPageToken", "")
                    if not next_token:
                        break

                    # Small delay between pages
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                except Exception as e:
                    logger.error(f"Error on page {page_num + 1} for '{keyword}': {e}")
                    break

            # Delay between keyword searches
            await asyncio.sleep(random.uniform(0.5, 1.5))

    logger.info(f"Scraped {len(listings)} listings for category '{category}'")
    return listings
