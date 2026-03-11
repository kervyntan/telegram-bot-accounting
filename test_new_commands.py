"""Test the new invoice management commands."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from src.mongo_storage import MongoInvoiceStorage
from src.models import InvoiceData

# Load environment variables
load_dotenv()

SGT = ZoneInfo("Asia/Singapore")


def test_new_features():
    """Test the new features: inception report, partial invoices, payment update."""
    # Initialize MongoDB storage
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("❌ MONGODB_URI not configured, skipping test")
        return

    storage = MongoInvoiceStorage(mongodb_uri, "telegram_bot")
    test_chat_id = "test_chat_123"

    print("🧪 Testing New Invoice Management Features\n")

    # Create test invoices with different payment statuses
    print("📝 Creating test invoices...")

    # Invoice 1: Fully paid
    invoice1 = InvoiceData.create(
        customer_name="John Doe",
        items=[
            {
                "name": "Widget A",
                "cost_price": "10.00",
                "sale_price": "20.00",
                "quantity": 5,
            }
        ],
        gst_rate=0.09,
        gst_threshold=400.0,
        deposit_paid="100.00",  # Fully paid
    )
    storage.add_invoice(invoice1, test_chat_id)
    print(f"  ✅ Created {invoice1.invoice_number} - PAID ($100 of $100)")

    # Invoice 2: Partial payment
    invoice2 = InvoiceData.create(
        customer_name="Jane Smith",
        items=[
            {
                "name": "Widget B",
                "cost_price": "50.00",
                "sale_price": "100.00",
                "quantity": 3,
            }
        ],
        gst_rate=0.09,
        gst_threshold=400.0,
        deposit_paid="150.00",  # Partial payment
    )
    storage.add_invoice(invoice2, test_chat_id)
    print(f"  ✅ Created {invoice2.invoice_number} - PARTIAL ($150 of $300)")

    # Invoice 3: Unpaid
    invoice3 = InvoiceData.create(
        customer_name="Bob Johnson",
        items=[
            {
                "name": "Widget C",
                "cost_price": "20.00",
                "sale_price": "40.00",
                "quantity": 10,
            }
        ],
        gst_rate=0.09,
        gst_threshold=400.0,
        deposit_paid="0.00",  # Unpaid (>= $400, so GST applies)
    )
    storage.add_invoice(invoice3, test_chat_id)
    print(
        f"  ✅ Created {invoice3.invoice_number} - UNPAID ($0 of ${invoice3.totals.grand_total:.2f})"
    )

    print("\n" + "=" * 60)

    # Test 1: Get all invoices (inception report)
    print("\n📊 Test 1: Inception Report (All-Time Summary)")
    summary = storage.get_all_invoices(test_chat_id)
    print(f"  Total Invoices: {summary['total_invoices']}")
    print(f"  Total Revenue: ${summary['total_revenue']:.2f}")
    print(f"  Amount Received: ${summary['total_received']:.2f}")
    print(f"  Outstanding: ${summary['total_outstanding']:.2f}")
    print(f"  Total Profit: ${summary['total_profit']:.2f}")
    print(f"  Payment Status:")
    print(f"    ✅ Paid: {summary['paid_count']}")
    print(f"    🔶 Partial: {summary['partial_count']}")
    print(f"    ⏳ Unpaid: {summary['unpaid_count']}")

    print("\n" + "=" * 60)

    # Test 2: Get partial invoices
    print("\n📋 Test 2: Partial Payment Invoices")
    partial_invoices = storage.get_partial_invoices(test_chat_id)
    print(f"  Found {len(partial_invoices)} partial payment invoice(s):")
    for inv in partial_invoices:
        print(f"\n  🔸 Invoice: {inv['invoice_number']}")
        print(f"    Customer: {inv['customer_name']}")
        print(f"    Grand Total: ${inv['grand_total']:.2f}")
        print(f"    Paid: ${inv['deposit_paid']:.2f}")
        print(f"    Balance Due: ${inv['balance_due']:.2f}")

    print("\n" + "=" * 60)

    # Test 3: Update payment
    print("\n💸 Test 3: Update Payment")
    print(f"  Updating {invoice2.invoice_number} deposit from $150 to $250...")
    success = storage.update_invoice_payment(invoice2.invoice_number, 250.00)

    if success:
        print("  ✅ Payment updated successfully!")

        # Verify the update
        updated_invoices = storage.get_partial_invoices(test_chat_id)
        updated_invoice = next(
            (
                inv
                for inv in storage.collection.find(
                    {"invoice_number": invoice2.invoice_number}
                )
            ),
            None,
        )

        if updated_invoice:
            print(f"  New deposit: ${updated_invoice['deposit_paid']:.2f}")
            print(f"  New balance: ${updated_invoice['balance_due']:.2f}")
            print(f"  New status: {updated_invoice['payment_status']}")
    else:
        print("  ❌ Payment update failed!")

    print("\n" + "=" * 60)

    # Test 4: Update to fully paid
    print("\n💰 Test 4: Mark Invoice as Fully Paid")
    print(f"  Updating {invoice3.invoice_number} to fully paid...")
    success = storage.update_invoice_payment(
        invoice3.invoice_number, invoice3.totals.grand_total
    )

    if success:
        print("  ✅ Payment updated successfully!")

        # Get updated inception report
        summary = storage.get_all_invoices(test_chat_id)
        print(f"\n  Updated Payment Status:")
        print(f"    ✅ Paid: {summary['paid_count']}")
        print(f"    🔶 Partial: {summary['partial_count']}")
        print(f"    ⏳ Unpaid: {summary['unpaid_count']}")
    else:
        print("  ❌ Payment update failed!")

    print("\n" + "=" * 60)

    # Cleanup - remove test invoices
    print("\n🧹 Cleaning up test data...")
    storage.collection.delete_many({"chat_id": test_chat_id})
    print("  ✅ Test data removed")

    storage.close()
    print("\n✅ All tests completed successfully!")


if __name__ == "__main__":
    test_new_features()
