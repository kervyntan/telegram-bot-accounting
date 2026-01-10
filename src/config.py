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

    # Business Details
    business_name: str = Field(default="Your Business", description="Business name")
    business_address: str = Field(default="Your Address", description="Business address")
    business_phone: str = Field(default="Your Phone", description="Business phone")
    business_email: str = Field(default="contact@business.com", description="Business email")
    business_registration: str = Field(default="", description="Business registration number")

    # GST Configuration
    gst_rate: Decimal = Field(default=Decimal("0.09"), description="GST rate (9% = 0.09)")
    gst_threshold: Decimal = Field(default=Decimal("400.00"), description="GST threshold amount")

    @property
    def invoices_dir(self) -> Path:
        """Get invoices directory path."""
        path = Path(__file__).parent.parent / "invoices"
        path.mkdir(exist_ok=True)
        return path


def load_settings() -> Settings:
    """Load and return application settings."""
    return Settings()
