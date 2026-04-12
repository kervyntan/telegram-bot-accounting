"""Configuration management using Pydantic settings."""

from decimal import Decimal
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot
    telegram_bot_token: str = Field(..., description="Telegram bot token from @BotFather")
    telegram_chat_id: int | None = Field(
        default=None, description="Your Telegram chat ID for automated reports"
    )
    webhook_url: str | None = Field(
        default=None,
        description="Public URL for Telegram webhook (e.g. https://your-app.vercel.app/api/webhook)",
    )

    # MongoDB Configuration
    mongodb_uri: str | None = Field(default=None, description="MongoDB connection URI")
    mongodb_database: str = Field(default="telegram_bot", description="MongoDB database name")

    # Business Details
    business_name: str = Field(default="Your Business", description="Business name")
    business_address: str = Field(default="Your Address", description="Business address")
    business_phone: str = Field(default="Your Phone", description="Business phone")
    business_email: str = Field(default="contact@business.com", description="Business email")
    business_registration: str = Field(default="", description="Business registration number")

    # GST Configuration
    gst_rate: Decimal = Field(default=Decimal("0.09"), description="GST rate (9% = 0.09)")
    gst_threshold: Decimal = Field(default=Decimal("400.00"), description="GST threshold amount")

    # Scraper Pipeline
    gemini_api_key: str | None = Field(
        default=None, description="Google Gemini API key for translation (free tier)"
    )
    catalogue_bot_token: str | None = Field(
        default=None, description="Catalogue bot token used for posting scraped listings"
    )
    scraper_channel_id: int | None = Field(
        default=None, description="Telegram channel/group ID for posting scraped listings"
    )
    scraper_topic_pokemon_promo: int | None = Field(
        default=None,
        description="Forum topic ID for Pokémon Promo card listings",
    )
    scraper_markup: float = Field(default=1.3, description="Price markup multiplier (1.3 = 30%)")
    scraper_min_price: float = Field(default=60.0, description="Minimum listing price in SGD")
    scraper_max_price: float = Field(default=1000.0, description="Maximum listing price in SGD")

    @property
    def invoices_dir(self) -> Path:
        """Get invoices directory path.

        Uses /tmp on serverless platforms (read-only filesystem).
        """
        import os

        if os.environ.get("VERCEL"):
            path = Path("/tmp/invoices")
        else:
            path = Path(__file__).parent.parent / "invoices"
        path.mkdir(exist_ok=True)
        return path


def load_settings() -> Settings:
    """Load and return application settings."""
    return Settings()


class CatalogueSettings(BaseSettings):
    """Settings for the public catalogue search bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Catalogue bot token (separate from accounting bot)
    catalogue_bot_token: str = Field(
        ..., description="Telegram bot token for the public catalogue search bot"
    )
    # Owner's chat ID — receives silent search notifications
    owner_chat_id: int | None = Field(
        default=None, description="Owner's chat ID for silent search notifications"
    )
    # Comma-separated list of group/channel chat IDs to index
    # Env var: CATALOGUE_GROUP_IDS (alias avoids _raw suffix mismatch)
    catalogue_group_ids_raw: str = Field(
        default="",
        alias="catalogue_group_ids",
        description="Comma-separated group chat IDs to index for listings",
    )
    # Owner's Telegram username (without @) — used for the DM CTA button in search results
    owner_username: str | None = Field(
        default=None, description="Owner's Telegram username (without @) for DM link"
    )
    # Webhook URL for the catalogue bot endpoint
    catalogue_webhook_url: str | None = Field(
        default=None,
        description="Public URL for catalogue bot webhook (e.g. https://your-app.vercel.app/api/catalogue_webhook)",
    )

    # Shared MongoDB (same cluster as accounting bot)
    mongodb_uri: str | None = Field(default=None, description="MongoDB connection URI")
    mongodb_database: str = Field(default="telegram_bot", description="MongoDB database name")

    @property
    def catalogue_group_ids(self) -> list[int]:
        """Parse comma-separated group IDs into a list of ints."""
        if not self.catalogue_group_ids_raw:
            return []
        return [int(x.strip()) for x in self.catalogue_group_ids_raw.split(",") if x.strip()]


def load_catalogue_settings() -> CatalogueSettings:
    """Load and return catalogue bot settings."""
    return CatalogueSettings()
