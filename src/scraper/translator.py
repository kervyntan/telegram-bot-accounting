"""Phase 3a: LLM-powered translation and title formatting using Google Gemini (free tier)."""

import asyncio
import json
import logging
import re

from google import genai

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an expert Pokémon and One Piece Trading Card appraiser. "
    "I will give you a JSON array of messy Japanese marketplace titles. "
    "For each title, extract the actual card name, set number/name, character, and condition/grade. "
    "Translate each into a clean, professional English e-commerce title. "
    "Ignore fluff words like 'super rare', 'discount', or 'must see'. "
    "Respond ONLY with a JSON array of the translated titles in the same order."
)

SINGLE_SYSTEM_PROMPT = (
    "You are an expert Pokémon and One Piece Trading Card appraiser. "
    "I will give you a messy Japanese marketplace title. "
    "Extract the actual card name, set number/name, character, and condition/grade. "
    "Translate it into a clean, professional English e-commerce title. "
    "Ignore fluff words like 'super rare', 'discount', or 'must see'. "
    "Respond ONLY with the finalized English title."
)


async def translate_titles_batch(
    raw_titles: list[str],
    api_key: str,
    model: str = "gemini-2.0-flash",
    max_retries: int = 8,
) -> list[str]:
    """Translate a batch of Japanese titles into English in a single API call."""
    client = genai.Client(api_key=api_key)

    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=json.dumps(raw_titles, ensure_ascii=False),
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=4096,
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            text = response.text.strip()
            translated = json.loads(text)
            if isinstance(translated, list) and len(translated) == len(raw_titles):
                logger.info(f"Batch translated {len(translated)} titles")
                return translated
            logger.warning(f"Batch translation returned {len(translated)} items, expected {len(raw_titles)}")
            return raw_titles
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse batch translation JSON (attempt {attempt + 1}): {text[:200]}...")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
                continue
            return raw_titles
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = 30 * (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(wait)
                continue
            logger.error(f"Batch translation failed: {e}")
            return raw_titles

    logger.error("Batch translation exhausted retries")
    return raw_titles


async def translate_title(
    raw_title: str,
    api_key: str,
    model: str = "gemini-2.0-flash",
    max_retries: int = 3,
) -> str:
    """Translate a single Japanese marketplace title into English."""
    client = genai.Client(api_key=api_key)

    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=raw_title,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SINGLE_SYSTEM_PROMPT,
                    max_output_tokens=150,
                    temperature=0.3,
                ),
            )
            translated = response.text.strip()
            logger.info(f"Translated: '{raw_title[:50]}...' -> '{translated}'")
            return translated
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = 10 * (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1})...")
                await asyncio.sleep(wait)
                continue
            logger.error(f"Translation failed for '{raw_title[:50]}...': {e}")
            return raw_title

    logger.error(f"Translation exhausted retries for '{raw_title[:50]}...'")
    return raw_title
