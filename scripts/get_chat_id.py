"""Helper script to get your Telegram chat ID."""

import asyncio

from telegram import Bot

from src.config import load_settings


async def get_updates():
    """Get recent updates to find chat ID."""
    settings = load_settings()
    bot = Bot(token=settings.telegram_bot_token)

    print("Fetching recent updates...")
    print("If you haven't sent a message to the bot yet, please:")
    print("1. Open Telegram")
    print("2. Send /start to your bot")
    print("3. Run this script again\n")

    try:
        updates = await bot.get_updates()

        if not updates:
            print("❌ No updates found. Please send a message to your bot first.")
            return

        print("✅ Found updates!\n")
        chat_ids = set()

        for update in updates:
            if update.message and update.message.chat:
                chat_id = update.message.chat.id
                chat_ids.add(chat_id)
                print(f"Chat ID: {chat_id}")
                print(f"  From: {update.message.from_user.first_name}")
                if update.message.from_user.username:
                    print(f"  Username: @{update.message.from_user.username}")
                print()

        if chat_ids:
            print("\n📋 To enable automated reports:")
            print("1. Copy your Chat ID from above")
            print("2. Add it to your .env file:")
            print(f"   TELEGRAM_CHAT_ID={list(chat_ids)[0]}")
            print("3. Restart the bot")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(get_updates())
