"""Telegram bot for invoice generation."""

import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings, load_settings
from .parser import MessageParseError, MessageParser
from .pdf_generator import InvoiceGenerator
from .storage import InvoiceStorage

try:
    from .mongo_storage import MongoInvoiceStorage

    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Singapore timezone
SGT = ZoneInfo("Asia/Singapore")


class InvoiceBot:
    """Telegram bot for generating invoices."""

    def __init__(self, settings: Settings) -> None:
        """Initialize bot with settings."""
        self.settings = settings
        self.parser = MessageParser(settings.gst_rate, settings.gst_threshold)
        self.generator = InvoiceGenerator(settings)

        # Initialize storage (prefer MongoDB if configured)
        if settings.mongodb_uri and MONGO_AVAILABLE:
            logger.info("Using MongoDB for invoice storage")
            self.storage = MongoInvoiceStorage(
                settings.mongodb_uri,
                settings.mongodb_database,
            )
        else:
            logger.info("Using JSON file storage for invoices")
            storage_path = settings.invoices_dir / "invoice_records.json"
            self.storage = InvoiceStorage(storage_path)

        # Build application
        self.app = Application.builder().token(settings.telegram_bot_token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("chatid", self.chatid_command))
        self.app.add_handler(CommandHandler("daily", self.daily_report_command))
        self.app.add_handler(CommandHandler("weekly", self.weekly_report_command))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        # Schedule daily and weekly reports
        job_queue = self.app.job_queue
        if job_queue:
            # Daily report at 7 PM SGT
            job_queue.run_daily(
                self.send_daily_report,
                time=time(hour=19, minute=0, tzinfo=SGT),
                name="daily_report",
            )

            # Weekly report on Fridays at 7 PM SGT
            job_queue.run_daily(
                self.send_weekly_report,
                time=time(hour=19, minute=0, tzinfo=SGT),
                days=(4,),  # Friday is day 4 (Monday=0)
                name="weekly_report",
            )

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command."""
        welcome_message = """👋 Welcome to Invoice Generator Bot!

I can help you generate professional invoices from simple messages.

📋 Commands:
/help - See message format and examples
/chatid - Get your chat ID for automated reports
/daily - Get today's P/L summary
/weekly - Get this week's P/L summary

📊 Automatic Reports:
• Daily report sent at 7 PM SGT
• Weekly report sent every Friday at 7 PM SGT"""

        await update.message.reply_text(welcome_message)

    async def chatid_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /chatid command."""
        if not update.message:
            return

        chat_id = update.message.chat_id
        message = f"""🆔 Your Chat ID: `{chat_id}`

To enable automated daily and weekly reports:
1. Copy your chat ID above
2. Add it to your .env file:
   `TELEGRAM_CHAT_ID={chat_id}`
3. Restart the bot

Reports will be sent automatically at 7 PM SGT."""

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Chat ID requested: {chat_id}")

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /help command."""
        help_message = self.parser.get_help_message()
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
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

            # Generate both PDFs (client and internal)
            client_pdf_path, internal_pdf_path = self.generator.generate_pdf(
                invoice_data
            )

            # Prepare caption
            caption = self._format_invoice_caption(invoice_data)

            # Send client PDF
            with open(client_pdf_path, "rb") as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=f"invoice_{invoice_data.invoice_number}_client.pdf",
                    caption=caption + "\n\n📄 Client Invoice (for customer)",
                )

            # Send internal PDF
            with open(internal_pdf_path, "rb") as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=f"invoice_{invoice_data.invoice_number}_internal.pdf",
                    caption="📊 Internal Invoice (with cost & profit details)",
                )

            # Save invoice to storage
            self.storage.add_invoice(invoice_data, update.message.chat_id)

            # Delete processing message
            await processing_msg.delete()

            # Clean up PDFs after sending
            await asyncio.sleep(5)
            if client_pdf_path.exists():
                client_pdf_path.unlink()
            if internal_pdf_path.exists():
                internal_pdf_path.unlink()

            logger.info(
                f"Invoices generated for chat {update.message.chat_id}: "
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
                "",
                f"💵 Subtotal: ${invoice_data.totals.subtotal:.2f}",
            ]
        )

        if invoice_data.totals.gst > 0:
            lines.append(f"📊 GST: ${invoice_data.totals.gst:.2f}")

        lines.append(f"💰 Grand Total: ${invoice_data.totals.grand_total:.2f}")

        # Show deposit and balance if applicable
        if invoice_data.totals.deposit_paid > 0:
            lines.extend(
                [
                    "",
                    f"💸 Deposit Paid: ${invoice_data.totals.deposit_paid:.2f}",
                    f"📋 Balance Due: ${invoice_data.totals.balance_due:.2f}",
                    f"📌 Status: {invoice_data.totals.payment_status}",
                ]
            )

        lines.extend(
            [
                "",
                f"📈 Profit: ${invoice_data.totals.total_profit:.2f}",
            ]
        )

        return "\n".join(lines)

    async def daily_report_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /daily command - manual trigger for daily report."""
        if not update.message:
            return

        chat_id = update.message.chat_id
        now = datetime.now(SGT)

        summary = self.storage.get_daily_summary(chat_id, now)
        message = self._format_daily_report(summary, now)

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def weekly_report_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /weekly command - manual trigger for weekly report."""
        if not update.message:
            return

        chat_id = update.message.chat_id
        now = datetime.now(SGT)

        summary = self.storage.get_weekly_summary(chat_id, now)
        message = self._format_weekly_report(summary, now)

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def send_daily_report(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send scheduled daily report to all active chats."""
        if not self.settings.telegram_chat_id:
            logger.warning("No chat ID configured for automated reports")
            return

        now = datetime.now(SGT)
        summary = self.storage.get_daily_summary(self.settings.telegram_chat_id, now)
        message = self._format_daily_report(summary, now)

        try:
            await context.bot.send_message(
                chat_id=self.settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info(f"Daily report sent to chat {self.settings.telegram_chat_id}")
        except Exception as e:
            logger.error(f"Failed to send daily report: {e}", exc_info=True)

    async def send_weekly_report(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send scheduled weekly report to all active chats."""
        if not self.settings.telegram_chat_id:
            logger.warning("No chat ID configured for automated reports")
            return

        now = datetime.now(SGT)
        summary = self.storage.get_weekly_summary(self.settings.telegram_chat_id, now)
        message = self._format_weekly_report(summary, now)

        try:
            await context.bot.send_message(
                chat_id=self.settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info(f"Weekly report sent to chat {self.settings.telegram_chat_id}")
        except Exception as e:
            logger.error(f"Failed to send weekly report: {e}", exc_info=True)

    def _format_daily_report(self, summary: dict, date: datetime) -> str:
        """Format daily report message."""
        lines = [
            "📊 *Daily P/L Report*",
            f"📅 Date: {date.strftime('%Y-%m-%d')}",
            "",
        ]

        if summary["total_invoices"] == 0:
            lines.append("No invoices generated today.")
        else:
            lines.extend(
                [
                    f"📝 Total Invoices: {summary['total_invoices']}",
                    "",
                    f"💵 Total Revenue: ${summary['total_revenue']:.2f}",
                    f"💸 Amount Received: ${summary['total_received']:.2f}",
                    f"📅 Outstanding: ${summary['total_outstanding']:.2f}",
                    "",
                    f"💰 Total Cost: ${summary['total_cost']:.2f}",
                    f"📈 Total Profit: ${summary['total_profit']:.2f}",
                    f"📊 Total GST: ${summary['total_gst']:.2f}",
                    "",
                ]
            )
            # Add payment status breakdown
            if summary["paid_count"] > 0 or summary["partial_count"] > 0:
                lines.append("📄 *Payment Status:*")
                if summary["paid_count"] > 0:
                    lines.append(f"  ✅ Paid: {summary['paid_count']}")
                if summary["partial_count"] > 0:
                    lines.append(f"  🔶 Partial: {summary['partial_count']}")
                if summary["unpaid_count"] > 0:
                    lines.append(f"  ⏳ Unpaid: {summary['unpaid_count']}")
                lines.append("")
            # Add profit margin
            if summary["total_revenue"] > 0:
                margin = summary["total_profit"] / summary["total_revenue"] * 100
                lines.append(f"📊 Profit Margin: {margin:.1f}%")
            else:
                lines.append("📊 Profit Margin: N/A")

        return "\n".join(lines)

    def _format_weekly_report(self, summary: dict, end_date: datetime) -> str:
        """Format weekly report message."""
        start_date = end_date - timedelta(days=7)

        lines = [
            "📊 *Weekly P/L Report*",
            f"📅 Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "",
        ]

        if summary["total_invoices"] == 0:
            lines.append("No invoices generated this week.")
        else:
            lines.extend(
                [
                    f"📝 Total Invoices: {summary['total_invoices']}",
                    "",
                    f"💵 Total Revenue: ${summary['total_revenue']:.2f}",
                    f"💸 Amount Received: ${summary['total_received']:.2f}",
                    f"📅 Outstanding: ${summary['total_outstanding']:.2f}",
                    "",
                    f"💰 Total Cost: ${summary['total_cost']:.2f}",
                    f"📈 Total Profit: ${summary['total_profit']:.2f}",
                    f"📊 Total GST: ${summary['total_gst']:.2f}",
                    "",
                ]
            )
            # Add payment status breakdown
            if summary["paid_count"] > 0 or summary["partial_count"] > 0:
                lines.append("📄 *Payment Status:*")
                if summary["paid_count"] > 0:
                    lines.append(f"  ✅ Paid: {summary['paid_count']}")
                if summary["partial_count"] > 0:
                    lines.append(f"  🔶 Partial: {summary['partial_count']}")
                if summary["unpaid_count"] > 0:
                    lines.append(f"  ⏳ Unpaid: {summary['unpaid_count']}")
                lines.append("")
            # Add profit margin and average
            if summary["total_revenue"] > 0:
                margin = summary["total_profit"] / summary["total_revenue"] * 100
                lines.append(f"📊 Profit Margin: {margin:.1f}%")
                avg = summary["total_revenue"] / summary["total_invoices"]
                lines.append(f"📊 Average Invoice Value: ${avg:.2f}")
            else:
                lines.append("📊 Profit Margin: N/A")

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
