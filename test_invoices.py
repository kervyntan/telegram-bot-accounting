"""Test script to generate sample invoices."""

from src.config import load_settings
from src.parser import MessageParser
from src.pdf_generator import InvoiceGenerator


def main():
    """Generate sample invoices."""
    settings = load_settings()
    parser = MessageParser(settings.gst_rate, settings.gst_threshold)
    generator = InvoiceGenerator(settings)

    # Sample invoice message
    message = """John Doe
---
Pokemon Card - Charizard VMAX | 50 | 120 | 2
Pokemon Card - Pikachu VSTAR | 30 | 75 | 3
Card Sleeves Ultra Pro | 5 | 15 | 5"""

    print("Parsing invoice message...")
    invoice_data = parser.parse_invoice_message(message)

    print(f"\nGenerating invoices for {invoice_data.invoice_number}...")
    client_pdf, internal_pdf = generator.generate_pdf(invoice_data)

    print(f"\n✅ Generated invoices:")
    print(f"   📄 Client PDF: {client_pdf}")
    print(f"   📊 Internal PDF: {internal_pdf}")
    print(f"\n💰 Grand Total: ${invoice_data.totals.grand_total:.2f}")
    print(f"📈 Total Profit: ${invoice_data.totals.total_profit:.2f}")


if __name__ == "__main__":
    main()
