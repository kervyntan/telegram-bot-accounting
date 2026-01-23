"""Test script to generate sample invoices."""

from decimal import Decimal

from src.config import load_settings
from src.parser import MessageParser
from src.pdf_generator import InvoiceGenerator


def main():
    """Generate sample invoices."""
    settings = load_settings()
    parser = MessageParser(settings.gst_rate, settings.gst_threshold)
    generator = InvoiceGenerator(settings)

    # Sample invoice message WITH DEPOSIT
    message = """John Doe
Deposit: 150.00
---
Pokemon Card - Charizard VMAX | 50 | 120 | 2
Pokemon Card - Pikachu VSTAR | 30 | 75 | 3
Card Sleeves Ultra Pro | 5 | 15 | 5"""

    print("=" * 60)
    print("GENERATING INVOICE WITH DEPOSIT")
    print("=" * 60)
    print("\nParsing invoice message...")
    invoice_data = parser.parse_invoice_message(message)

    print(f"\n📄 Invoice: {invoice_data.invoice_number}")
    print(f"👤 Customer: {invoice_data.customer_name}")
    print(f"📅 Date: {invoice_data.date}")
    print(f"\n💰 Financial Summary:")
    print(f"   Subtotal: ${invoice_data.totals.subtotal:.2f}")
    print(f"   GST: ${invoice_data.totals.gst:.2f}")
    print(f"   Grand Total: ${invoice_data.totals.grand_total:.2f}")
    print(f"\n💸 Payment Status:")
    print(f"   Deposit Paid: ${invoice_data.totals.deposit_paid:.2f}")
    print(f"   Balance Due: ${invoice_data.totals.balance_due:.2f}")
    print(f"   Status: {invoice_data.totals.payment_status}")
    print(f"\n📈 Profit Analysis:")
    print(f"   Total Cost: ${invoice_data.totals.total_cost:.2f}")
    print(f"   Total Profit: ${invoice_data.totals.total_profit:.2f}")

    print(f"\nGenerating PDFs...")
    client_pdf, internal_pdf = generator.generate_pdf(invoice_data)

    print(f"\n✅ Generated invoices:")
    print(f"   📄 Client PDF: {client_pdf}")
    print(f"   📊 Internal PDF: {internal_pdf}")

    # Sample invoice WITHOUT DEPOSIT (fully paid)
    print("\n" + "=" * 60)
    print("GENERATING FULLY PAID INVOICE (NO DEPOSIT)")
    print("=" * 60)

    message2 = """Jane Smith
---
Gaming Keyboard | 50 | 120 | 1
Gaming Mouse | 30 | 80 | 1
Mouse Pad RGB | 10 | 25 | 2"""

    print("\nParsing invoice message...")
    invoice_data2 = parser.parse_invoice_message(message2)

    print(f"\n📄 Invoice: {invoice_data2.invoice_number}")
    print(f"👤 Customer: {invoice_data2.customer_name}")
    print(f"📅 Date: {invoice_data2.date}")
    print(f"\n💰 Financial Summary:")
    print(f"   Subtotal: ${invoice_data2.totals.subtotal:.2f}")
    print(f"   GST: ${invoice_data2.totals.gst:.2f}")
    print(f"   Grand Total: ${invoice_data2.totals.grand_total:.2f}")
    print(f"\n💸 Payment Status:")
    print(f"   Deposit Paid: ${invoice_data2.totals.deposit_paid:.2f}")
    print(f"   Balance Due: ${invoice_data2.totals.balance_due:.2f}")
    print(f"   Status: {invoice_data2.totals.payment_status}")

    print(f"\nGenerating PDFs...")
    client_pdf2, internal_pdf2 = generator.generate_pdf(invoice_data2)

    print(f"\n✅ Generated invoices:")
    print(f"   📄 Client PDF: {client_pdf2}")
    print(f"   📊 Internal PDF: {internal_pdf2}")

    print("\n" + "=" * 60)
    print("ALL INVOICES GENERATED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
