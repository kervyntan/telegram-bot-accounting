"""Public catalogue search bot for Telegram."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .catalogue_storage import CatalogueStorage
from .config import CatalogueSettings

logger = logging.getLogger(__name__)


class CatalogueBot:
    """Telegram bot for searching card listings indexed from group chats."""

    def __init__(self, settings: CatalogueSettings) -> None:
        self.settings = settings
        if settings.mongodb_uri:
            self.storage = CatalogueStorage(
                settings.mongodb_uri, settings.mongodb_database
            )
        else:
            raise RuntimeError("MONGODB_URI is required for the catalogue bot")

        self.app = (
            Application.builder().token(settings.catalogue_bot_token).build()
        )

        # — DM handlers (public users search here) —
        self.app.add_handler(
            CommandHandler(
                "start", self.start_command, filters=filters.ChatType.PRIVATE
            )
        )
        self.app.add_handler(
            CommandHandler(
                "search", self.search_command, filters=filters.ChatType.PRIVATE
            )
        )
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                self.text_search,
            )
        )

        # — Group handlers (index listings automatically) —
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
                self.index_message,
            )
        )
        self.app.add_handler(
            MessageHandler(
                filters.UpdateType.EDITED_MESSAGE & filters.ChatType.GROUPS,
                self.index_edited_message,
            )
        )

    # ── DM handlers ─────────────────────────────────────────────────────────

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text(
            "👋 Welcome to the Card Catalogue!\n\n"
            "Search for available listings by typing a card name, or use:\n"
            "/search <name>\n\n"
            "Example: `/search Charizard` or just type `Charizard`",
            parse_mode="Markdown",
        )

    async def search_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text(
                "Please provide a search term.\nExample: `/search Charizard`",
                parse_mode="Markdown",
            )
            return
        await self._do_search(update, query)

    async def text_search(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await self._do_search(update, update.message.text.strip())

    async def _do_search(self, update: Update, query: str) -> None:
        user = update.effective_user
        user_label = f"@{user.username}" if user.username else user.full_name

        # Log the search and silently notify owner
        self.storage.log_search(user.id, user_label, query)
        await self._notify_owner(user.id, user_label, query)

        results = self.storage.search(query)
        if not results:
            await update.message.reply_text(
                f"No available listings found for *{query}*.",
                parse_mode="Markdown",
            )
            return

        lines = [f"🔍 Results for *{query}*:\n"]
        for r in results:
            snippet = r["text"][:200].replace("*", "").replace("_", "")
            seller = r.get("sender_name", "unknown")
            lines.append(f"• {snippet}\n  — listed by {seller}")

        # Build DM CTA button if owner username is configured
        keyboard = None
        if self.settings.owner_username:
            keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        "💬 DM Seller",
                        url=f"https://t.me/{self.settings.owner_username}",
                    )
                ]]
            )

        await update.message.reply_text(
            "\n\n".join(lines),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    async def _notify_owner(
        self, user_id: int, user_label: str, query: str
    ) -> None:
        """Send a silent notification to the owner about a search."""
        if not self.settings.owner_chat_id:
            return
        try:
            await self.app.bot.send_message(
                chat_id=self.settings.owner_chat_id,
                text=f"🔔 {user_label} (ID: `{user_id}`) searched: *{query}*",
                parse_mode="Markdown",
                disable_notification=True,
            )
        except Exception:
            logger.warning("Could not notify owner", exc_info=True)

    # ── Group indexing handlers ──────────────────────────────────────────────

    async def index_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Index a new group message as a catalogue listing."""
        msg = update.message
        if not msg or msg.chat_id not in self.settings.catalogue_group_ids:
            return
        sender = msg.from_user
        self.storage.upsert_listing(
            chat_id=msg.chat_id,
            message_id=msg.message_id,
            sender_id=sender.id if sender else 0,
            sender_name=(
                f"@{sender.username}" if sender and sender.username
                else (sender.full_name if sender else "unknown")
            ),
            text=msg.text,
        )

    async def index_edited_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Re-index an edited group message (status may have changed)."""
        msg = update.edited_message
        if not msg or msg.chat_id not in self.settings.catalogue_group_ids:
            return
        self.storage.mark_edited(
            chat_id=msg.chat_id,
            message_id=msg.message_id,
            new_text=msg.text or "",
        )

    # ── Webhook lifecycle ────────────────────────────────────────────────────

    async def setup_webhook(self) -> None:
        """Initialise the Application and register the webhook with Telegram."""
        await self.app.initialize()
        await self.app.start()
        if self.settings.catalogue_webhook_url:
            await self.app.bot.set_webhook(
                url=self.settings.catalogue_webhook_url,
                allowed_updates=Update.ALL_TYPES,
            )
            logger.info(
                f"Catalogue webhook set to {self.settings.catalogue_webhook_url}"
            )

    async def process_update(self, payload: dict) -> None:
        """Deserialise a Telegram update dict and dispatch it."""
        update = Update.de_json(payload, self.app.bot)
        await self.app.process_update(update)
