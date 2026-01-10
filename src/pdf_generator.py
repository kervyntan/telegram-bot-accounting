"""PDF invoice generator using ReportLab."""

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from .config import Settings
from .models import InvoiceData


class InvoiceGenerator:
    """Generate PDF invoices."""

    def __init__(self, settings: Settings) -> None:
        """Initialize generator with settings."""
        self.settings = settings

    def generate_pdf(self, invoice_data: InvoiceData) -> Path:
        """
        Generate PDF invoice.

        Args:
            invoice_data: Invoice data to generate PDF from

        Returns:
            Path to generated PDF file
        """
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"invoice_{invoice_data.invoice_number}_{timestamp}.pdf"
        filepath = self.settings.invoices_dir / filename

        # Create PDF
        c = canvas.Canvas(str(filepath), pagesize=A4)
        width, height = A4

        # Draw invoice
        self._draw_header(c, width, height)
        self._draw_invoice_details(c, invoice_data, height)
        self._draw_items_table(c, invoice_data, height)
        self._draw_totals(c, invoice_data, width, height)
        self._draw_footer(c, width, height)

        c.save()
        return filepath

    def _draw_header(self, c: canvas.Canvas, width: float, height: float) -> None:
        """Draw invoice header with business details."""
        # Business name
        c.setFont("Helvetica-Bold", 20)
        c.drawString(30 * mm, height - 30 * mm, self.settings.business_name)

        # Business details
        c.setFont("Helvetica", 10)
        y = height - 40 * mm
        c.drawString(30 * mm, y, self.settings.business_address)
        y -= 4 * mm
        c.drawString(30 * mm, y, self.settings.business_phone)
        y -= 4 * mm
        c.drawString(30 * mm, y, self.settings.business_email)

        if self.settings.business_registration:
            y -= 4 * mm
            c.drawString(30 * mm, y, f"Reg: {self.settings.business_registration}")

        # INVOICE title
        c.setFont("Helvetica-Bold", 24)
        c.drawRightString(width - 30 * mm, height - 30 * mm, "INVOICE")

    def _draw_invoice_details(
        self, c: canvas.Canvas, invoice_data: InvoiceData, height: float
    ) -> None:
        """Draw invoice details (number, date, customer)."""
        y = height - 65 * mm

        c.setFont("Helvetica-Bold", 10)
        c.drawString(30 * mm, y, "Invoice Number:")
        c.setFont("Helvetica", 10)
        c.drawString(60 * mm, y, invoice_data.invoice_number)

        y -= 5 * mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(30 * mm, y, "Date:")
        c.setFont("Helvetica", 10)
        c.drawString(60 * mm, y, invoice_data.date)

        if invoice_data.customer_name:
            y -= 5 * mm
            c.setFont("Helvetica-Bold", 10)
            c.drawString(30 * mm, y, "Customer:")
            c.setFont("Helvetica", 10)
            c.drawString(60 * mm, y, invoice_data.customer_name)

    def _draw_items_table(self, c: canvas.Canvas, invoice_data: InvoiceData, height: float) -> None:
        """Draw items table."""
        y = height - 95 * mm

        # Table headers
        headers = ["Item", "Cost Price", "Sale Price", "Qty", "Amount"]
        col_widths = [70 * mm, 25 * mm, 25 * mm, 15 * mm, 25 * mm]

        # Prepare data
        data = [headers]
        for item in invoice_data.items:
            data.append(
                [
                    item.name,
                    f"${item.cost_price:.2f}",
                    f"${item.sale_price:.2f}",
                    str(item.quantity),
                    f"${item.amount:.2f}",
                ]
            )

        # Create table
        table = Table(data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    # Header styling
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    # Body styling
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("TOPPADDING", (0, 1), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                    # Grid
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    # Alternating rows
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]
            )
        )

        # Draw table
        table.wrapOn(c, 160 * mm, 200 * mm)
        table.drawOn(c, 30 * mm, y - len(data) * 10 * mm)

    def _draw_totals(
        self, c: canvas.Canvas, invoice_data: InvoiceData, width: float, height: float
    ) -> None:
        """Draw totals section."""
        x = width - 80 * mm
        y = height - 200 * mm

        c.setFont("Helvetica-Bold", 10)

        # Subtotal
        c.drawString(x, y, "Subtotal:")
        c.drawRightString(width - 30 * mm, y, f"${invoice_data.totals.subtotal:.2f}")
        y -= 6 * mm

        # GST if applicable
        if invoice_data.totals.gst > 0:
            gst_percent = int(self.settings.gst_rate * 100)
            c.drawString(x, y, f"GST ({gst_percent}%):")
            c.drawRightString(width - 30 * mm, y, f"${invoice_data.totals.gst:.2f}")
            y -= 6 * mm

        # Line
        c.line(x, y, width - 30 * mm, y)
        y -= 6 * mm

        # Grand total
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, "Grand Total:")
        c.drawRightString(width - 30 * mm, y, f"${invoice_data.totals.grand_total:.2f}")
        y -= 10 * mm

        # Profit information
        c.setFont("Helvetica", 9)
        c.drawString(x, y, f"Total Cost: ${invoice_data.totals.total_cost:.2f}")
        y -= 4 * mm
        c.drawString(x, y, f"Total Profit: ${invoice_data.totals.total_profit:.2f}")

    def _draw_footer(self, c: canvas.Canvas, width: float, height: float) -> None:
        """Draw footer."""
        c.setFont("Helvetica", 8)
        footer_text = "Thank you for your business!"
        text_width = c.stringWidth(footer_text, "Helvetica", 8)
        c.drawString((width - text_width) / 2, 20 * mm, footer_text)
