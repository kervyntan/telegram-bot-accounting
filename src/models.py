"""Pydantic models for invoice data."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class InvoiceItem(BaseModel):
    """Model for an invoice item."""

    name: str = Field(..., min_length=1, max_length=200, description="Item name")
    cost_price: Decimal = Field(..., ge=0, description="Cost price per unit")
    sale_price: Decimal = Field(..., ge=0, description="Sale price per unit")
    quantity: int = Field(..., ge=1, description="Quantity")

    @field_validator("cost_price", "sale_price", mode="before")
    @classmethod
    def parse_decimal(cls, v: str | float | Decimal) -> Decimal:
        """Parse decimal from various input types."""
        if isinstance(v, str):
            # Remove currency symbols and spaces
            v = v.replace("$", "").replace(",", "").strip()
        return Decimal(str(v))

    @property
    def amount(self) -> Decimal:
        """Calculate total amount for this item."""
        return self.sale_price * self.quantity

    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost for this item."""
        return self.cost_price * self.quantity

    @property
    def profit(self) -> Decimal:
        """Calculate profit for this item."""
        return self.amount - self.total_cost


class InvoiceTotals(BaseModel):
    """Model for invoice totals."""

    subtotal: Decimal = Field(..., description="Subtotal before GST")
    gst: Decimal = Field(..., ge=0, description="GST amount")
    grand_total: Decimal = Field(..., description="Grand total including GST")
    total_cost: Decimal = Field(..., description="Total cost of all items")
    total_profit: Decimal = Field(..., description="Total profit")
    deposit_paid: Decimal = Field(default=Decimal("0"), ge=0, description="Deposit amount paid")
    balance_due: Decimal = Field(..., description="Remaining balance due")

    @property
    def is_fully_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.balance_due == 0

    @property
    def payment_status(self) -> str:
        """Get payment status string."""
        if self.is_fully_paid:
            return "PAID"
        elif self.deposit_paid > 0:
            return "PARTIAL"
        else:
            return "UNPAID"


class InvoiceData(BaseModel):
    """Model for complete invoice data."""

    invoice_number: str = Field(..., description="Unique invoice number")
    date: str = Field(..., description="Invoice date")
    customer_name: str | None = Field(None, description="Customer name")
    items: list[InvoiceItem] = Field(..., min_length=1, description="List of invoice items")
    totals: InvoiceTotals = Field(..., description="Invoice totals")

    @classmethod
    def create(
        cls,
        customer_name: str | None,
        items: list[InvoiceItem],
        gst_rate: Decimal,
        gst_threshold: Decimal,
        deposit_paid: Decimal = Decimal("0"),
    ) -> "InvoiceData":
        """Create invoice data with calculated totals."""
        # Calculate totals
        total_cost = sum(item.total_cost for item in items)
        subtotal = sum(item.amount for item in items)
        total_profit = subtotal - total_cost

        # Apply GST if threshold is met
        gst = Decimal("0")
        if subtotal >= gst_threshold:
            gst = subtotal * gst_rate

        grand_total = subtotal + gst
        balance_due = grand_total - deposit_paid

        # Generate invoice number
        invoice_number = cls.generate_invoice_number()

        # Format date
        date_str = datetime.now().strftime("%B %d, %Y")

        totals = InvoiceTotals(
            subtotal=subtotal.quantize(Decimal("0.01")),
            gst=gst.quantize(Decimal("0.01")),
            grand_total=grand_total.quantize(Decimal("0.01")),
            total_cost=total_cost.quantize(Decimal("0.01")),
            total_profit=total_profit.quantize(Decimal("0.01")),
            deposit_paid=deposit_paid.quantize(Decimal("0.01")),
            balance_due=balance_due.quantize(Decimal("0.01")),
        )

        return cls(
            invoice_number=invoice_number,
            date=date_str,
            customer_name=customer_name,
            items=items,
            totals=totals,
        )

    @staticmethod
    def generate_invoice_number() -> str:
        """Generate unique invoice number."""
        now = datetime.now()
        random_suffix = now.microsecond % 10000
        return f"INV-{now.strftime('%Y%m%d')}-{random_suffix:04d}"
