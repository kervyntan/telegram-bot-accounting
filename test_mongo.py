"""Test MongoDB connection and storage."""

from datetime import datetime
from decimal import Decimal

from src.config import load_settings
from src.models import InvoiceData, InvoiceItem
from src.mongo_storage import MongoInvoiceStorage


def test_mongo():
    """Test MongoDB storage."""
    settings = load_settings()

    if not settings.mongodb_uri:
        print("❌ MongoDB URI not configured in .env")
        return

    print("Connecting to MongoDB...")
    storage = MongoInvoiceStorage(settings.mongodb_uri, settings.mongodb_database)

    # Create test invoice with deposit
    items = [
        InvoiceItem(name="Test Item 1", cost_price=10, sale_price=20, quantity=2),
        InvoiceItem(name="Test Item 2", cost_price=50, sale_price=100, quantity=1),
    ]

    invoice = InvoiceData.create(
        customer_name="Test Customer",
        items=items,
        gst_rate=Decimal("0.09"),
        gst_threshold=Decimal("400"),
        deposit_paid=Decimal("50.00"),
    )

    print("\n✅ Connected successfully!")
    print(f"\nStoring test invoice...")
    print(f"  Invoice: {invoice.invoice_number}")
    print(f"  Grand Total: ${invoice.totals.grand_total:.2f}")
    print(f"  Deposit Paid: ${invoice.totals.deposit_paid:.2f}")
    print(f"  Balance Due: ${invoice.totals.balance_due:.2f}")
    print(f"  Status: {invoice.totals.payment_status}")

    storage.add_invoice(invoice, chat_id=12345)
    print("\n✅ Invoice stored in MongoDB!")

    # Test retrieval
    print("\nFetching daily summary...")
    now = datetime.now()
    daily = storage.get_daily_summary(12345, now)

    print(f"\n📊 Daily Summary:")
    print(f"  Total Invoices: {daily['total_invoices']}")
    print(f"  Total Revenue: ${daily['total_revenue']:.2f}")
    print(f"  Amount Received: ${daily['total_received']:.2f}")
    print(f"  Outstanding: ${daily['total_outstanding']:.2f}")
    print(f"  Total Profit: ${daily['total_profit']:.2f}")
    print(f"  Payment Status: {daily['paid_count']} paid, {daily['partial_count']} partial, {daily['unpaid_count']} unpaid")

    print("\n✅ MongoDB storage test completed successfully!")

    storage.close()


if __name__ == "__main__":
    test_mongo()
