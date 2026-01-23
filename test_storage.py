"""Test storage functionality."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from src.models import InvoiceData, InvoiceItem
from src.storage import InvoiceStorage


def test_storage():
    """Test storage and report generation."""
    # Create test storage
    storage = InvoiceStorage(Path("invoices/test_records.json"))

    # Create sample invoice
    items = [
        InvoiceItem(name="Test Item 1", cost_price=10, sale_price=20, quantity=2),
        InvoiceItem(name="Test Item 2", cost_price=50, sale_price=100, quantity=1),
    ]

    invoice = InvoiceData.create(
        invoice_number="TEST-001",
        date="2026-01-23",
        customer_name="Test Customer",
        items=items,
        gst_rate=Decimal("0.09"),
        gst_threshold=Decimal("400"),
    )

    # Store invoice
    print("Storing test invoice...")
    storage.add_invoice(invoice, chat_id=12345)

    # Get daily summary
    print("\nFetching daily summary...")
    now = datetime.now()
    daily = storage.get_daily_summary(12345, now)

    print(f"Total Invoices: {daily['total_invoices']}")
    print(f"Total Revenue: ${daily['total_revenue']:.2f}")
    print(f"Total Cost: ${daily['total_cost']:.2f}")
    print(f"Total Profit: ${daily['total_profit']:.2f}")

    # Get weekly summary
    print("\nFetching weekly summary...")
    weekly = storage.get_weekly_summary(12345, now)

    print(f"Total Invoices: {weekly['total_invoices']}")
    print(f"Total Revenue: ${weekly['total_revenue']:.2f}")
    print(f"Total Profit: ${weekly['total_profit']:.2f}")

    print("\n✅ Storage test completed successfully!")


if __name__ == "__main__":
    test_storage()
