"""Telegram bot for invoice generation."""

import asyncio
import logging
import re
from datetime import datetime, time, timedelta
from decimal import Decimal
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
from .models import CardPurchase
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
        self.app.add_handler(CommandHandler("inception", self.inception_report_command))
        self.app.add_handler(CommandHandler("partial", self.partial_invoices_command))
        self.app.add_handler(CommandHandler("payment", self.update_payment_command))
        self.app.add_handler(CommandHandler("buycard", self.buycard_command))
        self.app.add_handler(CommandHandler("cards", self.cards_command))
        self.app.add_handler(CommandHandler("sellcard", self.sellcard_command))
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
/inception - Get all-time P/L summary
/partial - Show all partial payment invoices
/payment - Update payment on an invoice
/buycard - Record a card purchase (inventory tracking)
/cards - Show all active card purchases
/sellcard - Mark card as sold (remove from P/L)

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

            # Build optional client name suffix for Telegram filename
            _client_name_part = ""
            if invoice_data.customer_name:
                _safe = re.sub(r"[^\w\s-]", "", invoice_data.customer_name).strip()
                _safe = re.sub(r"[\s]+", "_", _safe)
                if _safe:
                    _client_name_part = f"_{_safe}"

            # Send client PDF
            with open(client_pdf_path, "rb") as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=f"invoice_{invoice_data.invoice_number}{_client_name_part}_client.pdf",
                    caption=caption + "\n\n📄 Client Invoice (for customer)",
                )

            # Send internal PDF
            with open(internal_pdf_path, "rb") as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=f"invoice_{invoice_data.invoice_number}{_client_name_part}_internal.pdf",
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
            # Add card purchases info
            if summary.get("card_purchases", 0) > 0:
                lines.extend(
                    [
                        f"🎴 Active Card Purchases: {summary['card_purchases']}",
                        f"💳 Card Investment Cost: ${summary['card_cost']:.2f}",
                        "",
                    ]
                )
            # Add net profit
            lines.append(f"💎 Net Profit (after cards): ${summary['net_profit']:.2f}")
            lines.append("")
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
                invoice_margin = summary["total_profit"] / summary["total_revenue"] * 100
                lines.append(f"📊 Invoice Profit Margin: {invoice_margin:.1f}%")
                if summary["net_profit"] != summary["total_profit"]:
                    net_margin = summary["net_profit"] / summary["total_revenue"] * 100
                    lines.append(f"📊 Net Profit Margin: {net_margin:.1f}%")
                avg = summary["total_revenue"] / summary["total_invoices"]
                lines.append(f"📊 Average Invoice Value: ${avg:.2f}")
            else:
                lines.append("📊 Profit Margin: N/A")

        return "\n".join(lines)

    async def inception_report_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /inception command - all-time P/L report."""
        if not update.message:
            return

        chat_id = update.message.chat_id
        summary = self.storage.get_all_invoices(chat_id)

        lines = [
            "📊 *Inception P/L Report*",
            "📅 All-Time Summary",
            "",
        ]

        if summary["total_invoices"] == 0:
            lines.append("No invoices generated yet.")
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
            # Add card purchases info
            if summary.get("card_purchases", 0) > 0:
                lines.extend(
                    [
                        f"🎴 Active Card Purchases: {summary['card_purchases']}",
                        f"💳 Card Investment Cost: ${summary['card_cost']:.2f}",
                        "",
                    ]
                )
            # Add net profit
            lines.append(f"💎 Net Profit (after cards): ${summary['net_profit']:.2f}")
            lines.append("")
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
                invoice_margin = summary["total_profit"] / summary["total_revenue"] * 100
                lines.append(f"📊 Invoice Profit Margin: {invoice_margin:.1f}%")
                if summary.get("net_profit", summary["total_profit"]) != summary["total_profit"]:
                    net_margin = summary["net_profit"] / summary["total_revenue"] * 100
                    lines.append(f"📊 Net Profit Margin: {net_margin:.1f}%")
                avg = summary["total_revenue"] / summary["total_invoices"]
                lines.append(f"📊 Average Invoice Value: ${avg:.2f}")

        message = "\n".join(lines)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def partial_invoices_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /partial command - show all partial payment invoices."""
        if not update.message:
            return

        chat_id = update.message.chat_id
        invoices = self.storage.get_partial_invoices(chat_id)

        lines = [
            "📋 *Partial Payment Invoices*",
            "",
        ]

        if not invoices:
            lines.append("No invoices with partial payments found.")
        else:
            lines.append(f"Found {len(invoices)} invoice(s) with partial payments:")
            lines.append("")
            for inv in invoices:
                date_str = inv["timestamp"].strftime("%Y-%m-%d")
                lines.extend(
                    [
                        f"🔸 Invoice: *{inv['invoice_number']}*",
                        f"  👤 Customer: {inv['customer_name']}",
                        f"  📅 Date: {date_str}",
                        f"  💵 Grand Total: ${inv['grand_total']:.2f}",
                        f"  💸 Paid: ${inv['deposit_paid']:.2f}",
                        f"  📅 Balance Due: ${inv['balance_due']:.2f}",
                        "",
                    ]
                )

        message = "\n".join(lines)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def update_payment_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /payment command - update deposit amount for an invoice."""
        if not update.message or not context.args:
            help_message = (
                "Usage: /payment <invoice_number> <new_deposit_amount>\n\n"
                "Example: /payment INV-001 500.00"
            )
            if update.message:
                await update.message.reply_text(help_message)
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Please provide both invoice number and deposit amount.\n"
                "Example: /payment INV-001 500.00"
            )
            return

        invoice_number = context.args[0]
        try:
            new_deposit = float(context.args[1])
            if new_deposit < 0:
                await update.message.reply_text("Deposit amount cannot be negative.")
                return
        except ValueError:
            await update.message.reply_text(
                "Invalid deposit amount. Please provide a valid number.\n"
                "Example: /payment INV-001 500.00"
            )
            return

        success = self.storage.update_invoice_payment(invoice_number, new_deposit)

        if success:
            await update.message.reply_text(
                f"✅ Successfully updated payment for invoice *{invoice_number}*\n"
                f"New deposit amount: ${new_deposit:.2f}",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                f"❌ Invoice *{invoice_number}* not found.\n"
                "Please check the invoice number and try again.",
                parse_mode=ParseMode.MARKDOWN,
            )

    async def buycard_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /buycard command - add a card purchase for inventory tracking."""
        if not update.message or not context.args:
            help_message = (
                "🃏 *Card Purchase Tracking*\n\n"
                "Track cards purchased for future sale (inventory/investment).\n\n"
                "Usage: /buycard <card_name> | <price> | <quantity> | [notes]\n\n"
                "Examples:\n"
                "• /buycard Charizard VMAX | 150 | 2\n"
                "• /buycard Pikachu Gold Star | 500.50 | 1 | PSA 10\n"
                "• /buycard Pokemon Booster Box | 120 | 5 | Vivid Voltage\n\n"
                "Notes are optional. Prices can include $ or not."
            )
            if update.message:
                await update.message.reply_text(
                    help_message, parse_mode=ParseMode.MARKDOWN
                )
            return

        # Join all args and parse
        full_text = " ".join(context.args)
        parts = [p.strip() for p in full_text.split("|")]

        if len(parts) < 3:
            await update.message.reply_text(
                "❌ Invalid format. Use: /buycard <card_name> | <price> | <quantity> | [notes]\n\n"
                "Example: /buycard Charizard VMAX | 150 | 2",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        card_name = parts[0]
        notes = parts[3] if len(parts) > 3 else None

        try:
            # Parse price (remove $ and commas)
            price_str = parts[1].replace("$", "").replace(",", "").strip()
            purchase_price = Decimal(price_str)

            if purchase_price < 0:
                await update.message.reply_text("❌ Price cannot be negative.")
                return

            # Parse quantity
            quantity = int(parts[2])
            if quantity < 1:
                await update.message.reply_text("❌ Quantity must be at least 1.")
                return

        except (ValueError, IndexError) as e:
            await update.message.reply_text(
                f"❌ Error parsing price or quantity: {e}\n\n"
                "Make sure price is a valid number and quantity is an integer."
            )
            return

        # Create card purchase record
        try:
            card_data = CardPurchase.create(
                card_name=card_name,
                purchase_price=purchase_price,
                quantity=quantity,
                notes=notes,
            )

            # Save to storage
            self.storage.add_card(card_data, update.message.chat_id)

            # Format response
            response_lines = [
                "✅ *Card Purchase Recorded!*",
                "",
                f"🃏 Card: {card_data.card_name}",
                f"🆔 ID: {card_data.card_id}",
                f"💵 Price per card: ${card_data.purchase_price:.2f}",
                f"📦 Quantity: {card_data.quantity}",
                f"💰 Total Cost: ${card_data.total_cost:.2f}",
                f"📅 Date: {card_data.purchase_date}",
            ]

            if card_data.notes:
                response_lines.append(f"📝 Notes: {card_data.notes}")

            await update.message.reply_text(
                "\n".join(response_lines), parse_mode=ParseMode.MARKDOWN
            )

            logger.info(
                f"Card purchase recorded for chat {update.message.chat_id}: "
                f"{card_data.card_id} - {card_data.card_name}"
            )

        except Exception as e:
            await update.message.reply_text(
                f"❌ Error recording card purchase: {e}\n\nPlease try again."
            )
            logger.error(
                f"Error recording card purchase in chat {update.message.chat_id}: {e}",
                exc_info=True,
            )

    async def cards_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /cards command - show active card purchases."""
        if not update.message:
            return

        chat_id = update.message.chat_id
        cards = self.storage.get_active_cards(chat_id)

        lines = [
            "🃏 *Active Card Inventory*",
            "",
        ]

        if not cards:
            lines.append("No active card purchases.")
            lines.append("")
            lines.append("Use /buycard to add card purchases for tracking.")
        else:
            # Calculate totals
            total_cost = sum(card["total_cost"] for card in cards)
            total_quantity = sum(card["quantity"] for card in cards)

            lines.extend(
                [
                    "📊 *Summary:*",
                    f"• Total Active Purchases: {len(cards)}",
                    f"• Total Cards: {total_quantity}",
                    f"• Total Investment: ${total_cost:.2f}",
                    "",
                    "📋 *Active Purchases:*",
                    "",
                ]
            )

            # Show recent purchases (limit to last 20)
            for card in cards[:20]:
                date_str = card["timestamp"].strftime("%Y-%m-%d")
                lines.extend(
                    [
                        f"🔸 *{card['card_name']}*",
                        f"  🆔 {card['card_id']}",
                        f"  💵 ${card['purchase_price']:.2f} × "
                        f"{card['quantity']} = ${card['total_cost']:.2f}",
                        f"  📅 {date_str}",
                    ]
                )
                if card.get("notes"):
                    lines.append(f"  📝 {card['notes']}")
                lines.append("")

            if len(cards) > 20:
                lines.append(
                    f"_...and {len(cards) - 20} more purchases_"
                )
            
            lines.append("")
            lines.append("💡 Use /sellcard <card_id> to mark a card as sold")

        message = "\n".join(lines)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def sellcard_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /sellcard command - mark a card as sold."""
        if not update.message or not context.args:
            help_message = (
                "🔄 *Mark Card as Sold*\n\n"
                "Remove a card from your active inventory (exclude from P/L calculations).\n\n"
                "Usage: /sellcard <card_id>\n\n"
                "Example: /sellcard CARD-20260208-1234\n\n"
                "💡 Use /cards to see all active card IDs"
            )
            if update.message:
                await update.message.reply_text(
                    help_message, parse_mode=ParseMode.MARKDOWN
                )
            return

        card_id = context.args[0]

        try:
            success = self.storage.mark_card_as_sold(card_id)

            if success:
                await update.message.reply_text(
                    f"✅ Card *{card_id}* marked as sold!\n\n"
                    "It will no longer be included in P/L calculations.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                logger.info(
                    f"Card marked as sold in chat {update.message.chat_id}: {card_id}"
                )
            else:
                await update.message.reply_text(
                    f"❌ Card *{card_id}* not found.\n\n"
                    "Please check the card ID and try again.\n"
                    "Use /cards to see all active card IDs.",
                    parse_mode=ParseMode.MARKDOWN,
                )

        except Exception as e:
            await update.message.reply_text(
                f"❌ Error marking card as sold: {e}\n\nPlease try again."
            )
            logger.error(
                f"Error marking card as sold in chat {update.message.chat_id}: {e}",
                exc_info=True,
            )

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
