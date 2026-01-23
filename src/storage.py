"""Storage for invoice records using JSON."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import InvoiceData


class InvoiceStorage:
    """Store and retrieve invoice records."""

    def __init__(self, storage_path: Path) -> None:
        """Initialize storage with file path."""
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if it doesn't exist
        if not self.storage_path.exists():
            self._save_data([])

    def _load_data(self) -> list[dict[str, Any]]:
        """Load invoice records from file."""
        try:
            with open(self.storage_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_data(self, data: list[dict[str, Any]]) -> None:
        """Save invoice records to file."""
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def add_invoice(self, invoice_data: InvoiceData, chat_id: int) -> None:
        """Add an invoice record."""
        data = self._load_data()

        record = {
            "invoice_number": invoice_data.invoice_number,
            "date": invoice_data.date,
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "customer_name": invoice_data.customer_name,
            "subtotal": float(invoice_data.totals.subtotal),
            "gst": float(invoice_data.totals.gst),
            "grand_total": float(invoice_data.totals.grand_total),
            "total_cost": float(invoice_data.totals.total_cost),
            "total_profit": float(invoice_data.totals.total_profit),
            "items_count": len(invoice_data.items),
        }

        data.append(record)
        self._save_data(data)

    def get_invoices_by_date_range(
        self, chat_id: int, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Get invoices within a date range for a specific chat."""
        data = self._load_data()

        filtered = [
            record
            for record in data
            if record["chat_id"] == chat_id
            and start_date <= datetime.fromisoformat(record["timestamp"]) < end_date
        ]

        return filtered

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
                "total_cost": 0.0,
                "total_profit": 0.0,
                "total_gst": 0.0,
            }

        total_revenue = sum(Decimal(str(inv["grand_total"])) for inv in invoices)
        total_cost = sum(Decimal(str(inv["total_cost"])) for inv in invoices)
        total_profit = sum(Decimal(str(inv["total_profit"])) for inv in invoices)
        total_gst = sum(Decimal(str(inv["gst"])) for inv in invoices)

        return {
            "total_invoices": len(invoices),
            "total_revenue": float(total_revenue),
            "total_cost": float(total_cost),
            "total_profit": float(total_profit),
            "total_gst": float(total_gst),
            "invoices": invoices,
        }
