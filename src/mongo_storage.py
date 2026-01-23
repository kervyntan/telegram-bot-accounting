"""MongoDB storage for invoice records."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .models import InvoiceData


class MongoInvoiceStorage:
    """Store and retrieve invoice records using MongoDB."""

    def __init__(self, mongo_uri: str, database_name: str = "telegram_bot") -> None:
        """Initialize MongoDB connection."""
        self.client = MongoClient(mongo_uri)
        self.db: Database = self.client[database_name]
        self.invoices: Collection = self.db["invoices"]

        # Create indexes for better query performance
        self.invoices.create_index("chat_id")
        self.invoices.create_index("timestamp")
        self.invoices.create_index([("chat_id", 1), ("timestamp", -1)])

    def add_invoice(self, invoice_data: InvoiceData, chat_id: int) -> None:
        """Add an invoice record to MongoDB."""
        record = {
            "invoice_number": invoice_data.invoice_number,
            "date": invoice_data.date,
            "timestamp": datetime.now(),
            "chat_id": chat_id,
            "customer_name": invoice_data.customer_name,
            "subtotal": float(invoice_data.totals.subtotal),
            "gst": float(invoice_data.totals.gst),
            "grand_total": float(invoice_data.totals.grand_total),
            "deposit_paid": float(invoice_data.totals.deposit_paid),
            "balance_due": float(invoice_data.totals.balance_due),
            "payment_status": invoice_data.totals.payment_status,
            "total_cost": float(invoice_data.totals.total_cost),
            "total_profit": float(invoice_data.totals.total_profit),
            "items_count": len(invoice_data.items),
            "items": [
                {
                    "name": item.name,
                    "cost_price": float(item.cost_price),
                    "sale_price": float(item.sale_price),
                    "quantity": item.quantity,
                    "amount": float(item.amount),
                }
                for item in invoice_data.items
            ],
        }

        self.invoices.insert_one(record)

    def get_invoices_by_date_range(
        self, chat_id: int, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Get invoices within a date range for a specific chat."""
        # Remove timezone info for comparison if present
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        query = {
            "chat_id": chat_id,
            "timestamp": {"$gte": start_date, "$lt": end_date},
        }

        cursor = self.invoices.find(query).sort("timestamp", -1)
        return list(cursor)

    def get_daily_summary(self, chat_id: int, date: datetime) -> dict[str, Any]:
        """Get summary for a specific day."""
        # Get invoices from start of day to end of day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        invoices = self.get_invoices_by_date_range(chat_id, start_of_day, end_of_day)

        return self._calculate_summary(invoices)

    def get_weekly_summary(self, chat_id: int, end_date: datetime) -> dict[str, Any]:
        """Get summary for the past week (Friday 7pm to Friday 7pm)."""
        # Calculate start date (7 days before end_date)
        start_date = end_date - timedelta(days=7)

        invoices = self.get_invoices_by_date_range(chat_id, start_date, end_date)

        return self._calculate_summary(invoices)

    def _calculate_summary(self, invoices: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate summary statistics from invoice records."""
        if not invoices:
            return {
                "total_invoices": 0,
                "total_revenue": 0.0,
                "total_received": 0.0,
                "total_outstanding": 0.0,
                "total_cost": 0.0,
                "total_profit": 0.0,
                "total_gst": 0.0,
                "paid_count": 0,
                "partial_count": 0,
                "unpaid_count": 0,
            }

        total_revenue = sum(Decimal(str(inv["grand_total"])) for inv in invoices)
        total_cost = sum(Decimal(str(inv["total_cost"])) for inv in invoices)
        total_profit = sum(Decimal(str(inv["total_profit"])) for inv in invoices)
        total_gst = sum(Decimal(str(inv["gst"])) for inv in invoices)
        total_received = sum(Decimal(str(inv["deposit_paid"])) for inv in invoices)
        total_outstanding = sum(Decimal(str(inv["balance_due"])) for inv in invoices)

        # Count payment statuses
        paid_count = sum(1 for inv in invoices if inv.get("payment_status") == "PAID")
        partial_count = sum(
            1 for inv in invoices if inv.get("payment_status") == "PARTIAL"
        )
        unpaid_count = sum(
            1 for inv in invoices if inv.get("payment_status") == "UNPAID"
        )

        return {
            "total_invoices": len(invoices),
            "total_revenue": float(total_revenue),
            "total_received": float(total_received),
            "total_outstanding": float(total_outstanding),
            "total_cost": float(total_cost),
            "total_profit": float(total_profit),
            "total_gst": float(total_gst),
            "paid_count": paid_count,
            "partial_count": partial_count,
            "unpaid_count": unpaid_count,
            "invoices": invoices,
        }

    def close(self) -> None:
        """Close MongoDB connection."""
        self.client.close()
