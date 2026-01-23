"""Message parser for invoice data from Telegram messages."""

import re
from decimal import Decimal

from pydantic import ValidationError

from .models import InvoiceData, InvoiceItem


class MessageParseError(Exception):
    """Custom exception for message parsing errors."""

    pass


class MessageParser:
    """Parse invoice messages from Telegram."""

    def __init__(self, gst_rate: Decimal, gst_threshold: Decimal) -> None:
        """Initialize parser with GST settings."""
        self.gst_rate = gst_rate
        self.gst_threshold = gst_threshold

    def parse_invoice_message(self, message: str) -> InvoiceData:
        """
        Parse invoice message into InvoiceData.

        Expected format:
        ```
        Customer: John Doe
        ---
        Item Name | Cost Price | Sale Price | Quantity
        Product A | 10.00 | 15.00 | 2
        Product B | 25.50 | 35.00 | 1
        ---
        ```

        Or simplified:
        ```
        Item | Cost | Sale | Qty
        Product A | 10 | 15 | 2
        ```

        Args:
            message: Message text to parse

        Returns:
            InvoiceData object with parsed data

        Raises:
            MessageParseError: If parsing fails
        """
        try:
            lines = [line.strip() for line in message.split("\n") if line.strip()]

            if not lines:
                raise MessageParseError("Empty message")

            customer_name: str | None = None
            items: list[InvoiceItem] = []
            deposit_paid = Decimal("0")

            for line in lines:
                # Skip common headers
                if line.upper() in ("INVOICE", "---") or re.match(r"^-+$", line):
                    continue

                # Parse customer name
                if line.lower().startswith("customer:"):
                    customer_name = line[9:].strip()
                    continue

                # Parse deposit amount
                if line.lower().startswith("deposit:"):
                    deposit_str = line[8:].strip()
                    deposit_paid = self._parse_price(deposit_str)
                    continue

                # Skip header rows with "item" and "price"
                if "item" in line.lower() and "price" in line.lower():
                    continue

                # Parse item line (contains pipe separators)
                if "|" in line:
                    item = self._parse_item_line(line)
                    if item:
                        items.append(item)

            if not items:
                raise MessageParseError(
                    "No items found. Use format: Item | Cost | Sale | Qty"
                )

            # Create invoice with calculated totals
            return InvoiceData.create(
                customer_name=customer_name,
                items=items,
                gst_rate=self.gst_rate,
                gst_threshold=self.gst_threshold,
                deposit_paid=deposit_paid,
            )

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                error_messages.append(f"{field}: {error['msg']}")
            raise MessageParseError(
                f"Validation error: {'; '.join(error_messages)}"
            ) from e
        except MessageParseError:
            raise
        except Exception as e:
            raise MessageParseError(f"Failed to parse message: {e!s}") from e

    def _parse_item_line(self, line: str) -> InvoiceItem | None:
        """
        Parse a single item line.

        Args:
            line: Line containing item data separated by pipes

        Returns:
            InvoiceItem or None if parsing fails
        """
        parts = [p.strip() for p in line.split("|")]

        if len(parts) < 4:
            return None

        try:
            name = parts[0]
            cost_price = self._parse_price(parts[1])
            sale_price = self._parse_price(parts[2])
            quantity = self._parse_quantity(parts[3])

            return InvoiceItem(
                name=name,
                cost_price=cost_price,
                sale_price=sale_price,
                quantity=quantity,
            )
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_price(price_str: str) -> Decimal:
        """Parse price string to Decimal."""
        # Remove currency symbols, commas, and spaces
        cleaned = re.sub(r"[^\d.]", "", price_str)
        return Decimal(cleaned)

    @staticmethod
    def _parse_quantity(qty_str: str) -> int:
        """Parse quantity string to int."""
        # Remove non-digit characters
        cleaned = re.sub(r"\D", "", qty_str)
        return int(cleaned)

    def get_help_message(self) -> str:
        """Get help message with format instructions."""
        gst_percent = int(self.gst_rate * 100)
        return f"""📄 *Invoice Bot Help*

To generate an invoice, send me a message in this format:

```
Customer: John Doe
Deposit: 50.00
---
Item Name | Cost Price | Sale Price | Quantity
Product A | 10.00 | 15.00 | 2
Product B | 25.50 | 35.00 | 1
---
```

*Example with full payment:*
```
Customer: Jane Smith
---
Laptop Case | 15 | 25 | 1
USB Cable | 2.50 | 5 | 3
Mouse Pad | 3 | 8 | 2
```

*Example with deposit:*
```
Customer: Mike Johnson
Deposit: 100
---
Gaming Keyboard | 50 | 120 | 1
Gaming Mouse | 30 | 80 | 1
```

*Notes:*
• Customer name is optional
• Use pipe (|) to separate fields
• GST ({gst_percent}%) applies if total ≥ ${self.gst_threshold}
• Cost Price = your cost, Sale Price = selling price

Just send the message and I'll generate a PDF invoice!"""
