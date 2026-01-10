"""Setup script to configure Telegram webhook for Vercel deployment."""

import asyncio
import sys

from telegram import Bot

from src.config import load_settings


async def setup_webhook(webhook_url: str) -> None:
    """Set up Telegram webhook."""
    settings = load_settings()
    bot = Bot(token=settings.telegram_bot_token)

    try:
        # Remove existing webhook
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Removed existing webhook")

        # Set new webhook
        success = await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )

        if success:
            print(f"✅ Webhook set successfully: {webhook_url}")

            # Verify webhook
            webhook_info = await bot.get_webhook_info()
            print("\n📊 Webhook Info:")
            print(f"   URL: {webhook_info.url}")
            print(f"   Pending updates: {webhook_info.pending_update_count}")
            if webhook_info.last_error_message:
                print(f"   ⚠️  Last error: {webhook_info.last_error_message}")
        else:
            print("❌ Failed to set webhook")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


async def remove_webhook() -> None:
    """Remove Telegram webhook (for local development)."""
    settings = load_settings()
    bot = Bot(token=settings.telegram_bot_token)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook removed successfully")
        print("💡 You can now run the bot locally with polling")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


async def check_status() -> None:
    """Check current webhook status."""
    settings = load_settings()
    bot = Bot(token=settings.telegram_bot_token)

    try:
        webhook_info = await bot.get_webhook_info()
        print("📊 Webhook Status:")
        print(f"   URL: {webhook_info.url or 'Not set (using polling)'}")
        print(f"   Pending updates: {webhook_info.pending_update_count}")
        if webhook_info.last_error_date:
            print(f"   Last error date: {webhook_info.last_error_date}")
        if webhook_info.last_error_message:
            print(f"   ⚠️  Last error: {webhook_info.last_error_message}")
        if webhook_info.max_connections:
            print(f"   Max connections: {webhook_info.max_connections}")

        # Check bot info
        me = await bot.get_me()
        print("\n🤖 Bot Info:")
        print(f"   Username: @{me.username}")
        print(f"   Name: {me.first_name}")
        print(f"   ID: {me.id}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/setup_webhook.py <webhook-url>")
        print("  python scripts/setup_webhook.py remove")
        print("  python scripts/setup_webhook.py status")
        print("\nExample:")
        print("  python scripts/setup_webhook.py https://your-app.vercel.app/api/webhook")
        sys.exit(1)

    command = sys.argv[1]

    if command == "remove":
        asyncio.run(remove_webhook())
    elif command == "status":
        asyncio.run(check_status())
    else:
        webhook_url = command
        if not webhook_url.startswith("https://"):
            print("❌ Webhook URL must start with https://")
            sys.exit(1)
        asyncio.run(setup_webhook(webhook_url))


if __name__ == "__main__":
    main()
