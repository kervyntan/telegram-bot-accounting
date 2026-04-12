"""MongoDB storage for invoice records and scraper de-duplication."""

import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .models import CardPurchase, InvoiceData


class MongoInvoiceStorage:
    """Store and retrieve invoice records using MongoDB."""

    def __init__(self, mongo_uri: str, database_name: str = "telegram_bot") -> None:
        """Initialize MongoDB connection."""
        self.client = MongoClient(mongo_uri)
        self.db: Database = self.client[database_name]
        self.invoices: Collection = self.db["invoices"]
        self.cards: Collection = self.db["cards"]

        # Create indexes for better query performance
        self.invoices.create_index("chat_id")
        self.invoices.create_index("timestamp")
        self.invoices.create_index([("chat_id", 1), ("timestamp", -1)])

        # Create indexes for cards
        self.cards.create_index("chat_id")
        self.cards.create_index("timestamp")
        self.cards.create_index([("chat_id", 1), ("timestamp", -1)])

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
        cards = self.get_cards_by_date_range(chat_id, start_of_day, end_of_day)

        return self._calculate_summary(invoices, cards)

    def get_weekly_summary(self, chat_id: int, end_date: datetime) -> dict[str, Any]:
        """Get summary for the past week (Friday 7pm to Friday 7pm)."""
        # Calculate start date (7 days before end_date)
        start_date = end_date - timedelta(days=7)

        invoices = self.get_invoices_by_date_range(chat_id, start_date, end_date)
        cards = self.get_cards_by_date_range(chat_id, start_date, end_date)

        return self._calculate_summary(invoices, cards)

    def _calculate_summary(
        self, invoices: list[dict[str, Any]], cards: list[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Calculate summary statistics from invoice records and card purchases."""
        if cards is None:
            cards = []

        if not invoices and not cards:
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
                "card_purchases": 0,
                "card_cost": 0.0,
                "net_profit": 0.0,
            }

        total_revenue = sum(Decimal(str(inv["grand_total"])) for inv in invoices)
        total_cost = sum(Decimal(str(inv["total_cost"])) for inv in invoices)
        total_profit = sum(Decimal(str(inv["total_profit"])) for inv in invoices)
        total_gst = sum(Decimal(str(inv["gst"])) for inv in invoices)
        total_received = sum(Decimal(str(inv["deposit_paid"])) for inv in invoices)
        total_outstanding = sum(Decimal(str(inv["balance_due"])) for inv in invoices)

        # Count payment statuses
        paid_count = sum(1 for inv in invoices if inv.get("payment_status") == "PAID")
        partial_count = sum(1 for inv in invoices if inv.get("payment_status") == "PARTIAL")
        unpaid_count = sum(1 for inv in invoices if inv.get("payment_status") == "UNPAID")

        # Calculate card costs (only active/unsold cards)
        active_cards = [c for c in cards if c.get("status") == "active"]
        card_cost = sum(Decimal(str(card["total_cost"])) for card in active_cards)

        # Calculate net profit (invoice profit - card investment costs)
        net_profit = total_profit - card_cost

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
            "card_purchases": len(active_cards),
            "card_cost": float(card_cost),
            "net_profit": float(net_profit),
            "invoices": invoices,
        }

    def get_all_invoices(self, chat_id: int) -> dict[str, Any]:
        """Get all-time summary for inception report."""
        invoices = list(self.invoices.find({"chat_id": chat_id}).sort("timestamp", ASCENDING))
        cards = list(self.cards.find({"chat_id": chat_id}).sort("timestamp", ASCENDING))
        return self._calculate_summary(invoices, cards)

    def get_invoices_by_customer(self, chat_id: int, customer_name: str) -> list[dict[str, Any]]:
        """Get all invoices for a specific customer (case-insensitive)."""
        # Normalize whitespace before building the regex so stored names with
        # non-breaking spaces or extra whitespace still match
        normalized = " ".join(customer_name.split())
        # Escape regex metacharacters but NOT spaces (avoid re.escape which
        # escapes spaces and produces patterns MongoDB may not handle)
        pattern = re.sub(r"([.^$*+?{}\[\]\\|()])", r"\\\1", normalized)
        cursor = self.invoices.find(
            {
                "chat_id": chat_id,
                "customer_name": {"$regex": f"^{pattern}$", "$options": "i"},
            }
        ).sort("timestamp", ASCENDING)
        return list(cursor)

    def get_partial_invoices(self, chat_id: int) -> list[dict[str, Any]]:
        """Get all invoices with partial payment status."""
        return list(
            self.invoices.find({"chat_id": chat_id, "payment_status": "PARTIAL"}).sort(
                "timestamp", DESCENDING
            )
        )

    def update_invoice_payment(self, invoice_number: str, new_deposit: float) -> bool:
        """Update deposit amount and recalculate payment status for an invoice."""
        invoice = self.invoices.find_one({"invoice_number": invoice_number})
        if not invoice:
            return False

        grand_total = Decimal(str(invoice["grand_total"]))
        new_deposit_decimal = Decimal(str(new_deposit))
        balance_due = grand_total - new_deposit_decimal

        # Determine payment status
        if new_deposit_decimal >= grand_total:
            payment_status = "PAID"
            balance_due = Decimal("0")
        elif new_deposit_decimal > 0:
            payment_status = "PARTIAL"
        else:
            payment_status = "UNPAID"

        result = self.invoices.update_one(
            {"invoice_number": invoice_number},
            {
                "$set": {
                    "deposit_paid": float(new_deposit_decimal),
                    "balance_due": float(balance_due),
                    "payment_status": payment_status,
                }
            },
        )

        return result.modified_count > 0

    def add_card(self, card_data: CardPurchase, chat_id: int) -> None:
        """Add a card purchase record to MongoDB."""
        record = {
            "card_id": card_data.card_id,
            "card_name": card_data.card_name,
            "purchase_price": float(card_data.purchase_price),
            "quantity": card_data.quantity,
            "total_cost": float(card_data.total_cost),
            "purchase_date": card_data.purchase_date,
            "timestamp": card_data.timestamp,
            "chat_id": chat_id,
            "notes": card_data.notes,
            "status": card_data.status,
        }

        self.cards.insert_one(record)

    def get_cards_by_date_range(
        self, chat_id: int, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Get card purchases within a date range for a specific chat."""
        # Remove timezone info for comparison if present
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        query = {
            "chat_id": chat_id,
            "timestamp": {"$gte": start_date, "$lt": end_date},
        }

        cursor = self.cards.find(query).sort("timestamp", -1)
        return list(cursor)

    def get_all_cards(self, chat_id: int) -> list[dict[str, Any]]:
        """Get all card purchases for a specific chat."""
        cursor = self.cards.find({"chat_id": chat_id}).sort("timestamp", DESCENDING)
        return list(cursor)

    def get_cards_summary(self, chat_id: int) -> dict[str, Any]:
        """Get summary of all card purchases."""
        cards = self.get_all_cards(chat_id)

        if not cards:
            return {
                "total_cards": 0,
                "total_quantity": 0,
                "total_cost": 0.0,
                "cards": [],
            }

        total_cost = sum(Decimal(str(card["total_cost"])) for card in cards)
        total_quantity = sum(card["quantity"] for card in cards)

        return {
            "total_cards": len(cards),
            "total_quantity": total_quantity,
            "total_cost": float(total_cost),
            "cards": cards,
        }

    def mark_card_as_sold(self, card_id: str) -> bool:
        """Mark a card purchase as sold."""
        result = self.cards.update_one(
            {"card_id": card_id},
            {"$set": {"status": "sold"}},
        )
        return result.modified_count > 0

    def get_active_cards(self, chat_id: int) -> list[dict[str, Any]]:
        """Get all active (unsold) card purchases."""
        return list(
            self.cards.find({"chat_id": chat_id, "status": "active"}).sort("timestamp", DESCENDING)
        )

    def close(self) -> None:
        """Close MongoDB connection."""
        self.client.close()


class ScraperListingStorage:
    """Track sent scraper listings in MongoDB for de-duplication."""

    def __init__(self, mongo_uri: str, database_name: str = "telegram_bot") -> None:
        self.client = MongoClient(mongo_uri)
        self.db: Database = self.client[database_name]
        self.listings: Collection = self.db["scraper_listings"]

        self.listings.create_index("listing_id", unique=True)
        self.listings.create_index("sent_at")

    def get_seen_ids(self) -> set[str]:
        """Return all listing IDs that have already been sent."""
        return {doc["listing_id"] for doc in self.listings.find({}, {"listing_id": 1})}

    def mark_sent(self, listing_id: str, title: str, source_url: str) -> None:
        """Record a listing as sent."""
        self.listings.update_one(
            {"listing_id": listing_id},
            {
                "$set": {
                    "listing_id": listing_id,
                    "title": title,
                    "source_url": source_url,
                    "sent_at": datetime.now(),
                }
            },
            upsert=True,
        )

    def close(self) -> None:
        self.client.close()
