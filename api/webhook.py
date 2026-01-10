"""Vercel serverless function for Telegram webhook."""

import asyncio
import json
import logging
import os
import sys

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import load_settings
from src.parser import MessageParseError, MessageParser
from src.pdf_generator import InvoiceGenerator

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Global application instance (reused across invocations)
_app = None
_settings = None
_parser = None
_generator = None


def get_application():
    """Get or create the Telegram application instance."""
    global _app, _settings, _parser, _generator

    if _app is None:
        _settings = load_settings()
        _parser = MessageParser(_settings.gst_rate, _settings.gst_threshold)
        _generator = InvoiceGenerator(_settings)

        # Build application
        _app = Application.builder().token(_settings.telegram_bot_token).build()

        # Register handlers
        _app.add_handler(CommandHandler("start", start_command))
        _app.add_handler(CommandHandler("help", help_command))
        _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("Application initialized")

    return _app, _parser, _generator


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = """👋 Welcome to Invoice Generator Bot!

I can help you generate professional invoices from simple messages.

Use /help to see the message format and examples."""

    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    _, parser, _ = get_application()
    help_message = parser.get_help_message()
    await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    if not update.message or not update.message.text:
        return

    message_text = update.message.text.strip()
    if not message_text:
        return

    _, parser, generator = get_application()

    # Send processing message
    processing_msg = await update.message.reply_text("⏳ Generating invoice...")

    try:
        # Parse message
        invoice_data = parser.parse_invoice_message(message_text)

        # Generate PDF
        pdf_path = generator.generate_pdf(invoice_data)

        # Prepare caption
        caption = format_invoice_caption(invoice_data)

        # Send PDF
        with open(pdf_path, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename=pdf_path.name,
                caption=caption,
            )

        # Delete processing message
        await processing_msg.delete()

        # Clean up PDF
        if pdf_path.exists():
            pdf_path.unlink()

        logger.info(
            f"Invoice generated for chat {update.message.chat_id}: {invoice_data.invoice_number}"
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


def format_invoice_caption(invoice_data) -> str:
    """Format invoice caption for Telegram message."""
    lines = [
        "✅ Invoice generated!",
        "",
        f"📄 Invoice #{invoice_data.invoice_number}",
        f"📅 Date: {invoice_data.date}",
    ]

    if invoice_data.customer_name:
        lines.append(f"👤 Customer: {invoice_data.customer_name}")

    lines.extend([f"💵 Subtotal: ${invoice_data.totals.subtotal:.2f}"])

    if invoice_data.totals.gst > 0:
        lines.append(f"📊 GST: ${invoice_data.totals.gst:.2f}")

    lines.extend(
        [
            f"💰 Grand Total: ${invoice_data.totals.grand_total:.2f}",
            f"📈 Profit: ${invoice_data.totals.total_profit:.2f}",
        ]
    )

    return "\n".join(lines)


async def process_update(update_data: dict):
    """Process webhook update from Telegram."""
    try:
        application, _, _ = get_application()

        # Create Update object from webhook data
        update = Update.de_json(update_data, application.bot)

        if update:
            # Process the update
            await application.process_update(update)

        logger.info("Update processed successfully")

    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        raise


def handler(request):
    """Vercel serverless function handler."""
    try:
        # Get request method
        method = request.get("method", "GET")

        # Handle GET requests (health check)
        if method == "GET":
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "ok", "bot": "telegram-invoice-bot"}),
            }

        # Handle POST requests (webhook)
        if method == "POST":
            # Get request body
            body = request.get("body", "{}")
            if isinstance(body, str):
                update_data = json.loads(body)
            else:
                update_data = body

            logger.info(f"Received update: {update_data.get('update_id', 'unknown')}")

            # Process update asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_update(update_data))
            finally:
                loop.close()

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"ok": True}),
            }

        return {
            "statusCode": 405,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Method not allowed"}),
        }

    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
