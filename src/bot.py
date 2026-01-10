"""Telegram bot for invoice generation."""

import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .config import Settings, load_settings
from .parser import MessageParseError, MessageParser
from .pdf_generator import InvoiceGenerator

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class InvoiceBot:
    """Telegram bot for generating invoices."""

    def __init__(self, settings: Settings) -> None:
        """Initialize bot with settings."""
        self.settings = settings
        self.parser = MessageParser(settings.gst_rate, settings.gst_threshold)
        self.generator = InvoiceGenerator(settings)

        # Build application
        self.app = Application.builder().token(settings.telegram_bot_token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        welcome_message = """👋 Welcome to Invoice Generator Bot!

I can help you generate professional invoices from simple messages.

Use /help to see the message format and examples."""

        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_message = self.parser.get_help_message()
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages."""
        if not update.message or not update.message.text:
            return

        message_text = update.message.text.strip()
        if not message_text:
            return

        # Send processing message
        processing_msg = await update.message.reply_text("⏳ Generating invoice...")

        try:
            # Parse message
            invoice_data = self.parser.parse_invoice_message(message_text)

            # Generate PDF
            pdf_path = self.generator.generate_pdf(invoice_data)

            # Prepare caption
            caption = self._format_invoice_caption(invoice_data)

            # Send PDF
            with open(pdf_path, "rb") as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=pdf_path.name,
                    caption=caption,
                )

            # Delete processing message
            await processing_msg.delete()

            # Clean up PDF after sending
            await asyncio.sleep(5)
            if pdf_path.exists():
                pdf_path.unlink()

            logger.info(
                f"Invoice generated for chat {update.message.chat_id}: "
                f"{invoice_data.invoice_number}"
            )

        except MessageParseError as e:
            await processing_msg.edit_text(
                f"❌ Error parsing message: {e}\n\nUse /help to see the correct format."
            )
            logger.warning(f"Parse error in chat {update.message.chat_id}: {e}")
        except Exception as e:
            await processing_msg.edit_text(
                f"❌ Error generating invoice: {e}\n\nPlease try again or contact support."
            )
            logger.error(f"Error in chat {update.message.chat_id}: {e}", exc_info=True)

    def _format_invoice_caption(self, invoice_data) -> str:
        """Format invoice caption for Telegram message."""
        lines = [
            "✅ Invoice generated!",
            "",
            f"📄 Invoice #{invoice_data.invoice_number}",
            f"📅 Date: {invoice_data.date}",
        ]

        if invoice_data.customer_name:
            lines.append(f"👤 Customer: {invoice_data.customer_name}")

        lines.extend(
            [
                f"💵 Subtotal: ${invoice_data.totals.subtotal:.2f}",
            ]
        )

        if invoice_data.totals.gst > 0:
            lines.append(f"📊 GST: ${invoice_data.totals.gst:.2f}")

        lines.extend(
            [
                f"💰 Grand Total: ${invoice_data.totals.grand_total:.2f}",
                f"📈 Profit: ${invoice_data.totals.total_profit:.2f}",
            ]
        )

        return "\n".join(lines)

    def run(self) -> None:
        """Run the bot."""
        logger.info("Starting Invoice Bot...")
        logger.info(f"GST Rate: {int(self.settings.gst_rate * 100)}%")
        logger.info(f"GST Threshold: ${self.settings.gst_threshold}")
        logger.info("Bot is running. Press Ctrl+C to stop.")

        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    """Main entry point."""
    try:
        settings = load_settings()
        bot = InvoiceBot(settings)
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
