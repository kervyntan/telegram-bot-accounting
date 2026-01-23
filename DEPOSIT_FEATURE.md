# Deposit & Payment Tracking Enhancement

## Overview

The bot now supports deposit tracking and payment status management for invoices, with MongoDB persistence for data across deployments.

## New Features

### 1. Deposit Tracking
- **Specify deposits** in invoice messages
- **Payment status** automatically calculated (PAID/PARTIAL/UNPAID)
- **Balance due** shown on invoices and reports
- **Client invoices** show deposit and balance information
- **Internal invoices** include full cost and profit details

### 2. MongoDB Integration
- **Persistent storage** using MongoDB Atlas
- **Data survives** bot restarts and redeployments
- **Better performance** with indexed queries
- **Fallback** to JSON file storage if MongoDB not configured

### 3. Enhanced P/L Reports
- **Amount Received**: Total deposits/payments collected
- **Outstanding Balance**: Total amount still owed
- **Payment Status Breakdown**: Count of paid/partial/unpaid invoices
- **Revenue vs Received**: See total billed vs actual cash received

## Usage

### Creating Invoice with Deposit

```
Customer: John Doe
Deposit: 150.00
---
Pokemon Card | 50 | 120 | 2
Gaming Mouse | 30 | 80 | 1
```

### Creating Invoice Without Deposit (Unpaid)

```
Customer: Jane Smith
---
Laptop Case | 15 | 25 | 1
USB Cable | 2.50 | 5 | 3
```

### Creating Fully Paid Invoice

Set deposit equal to grand total, or omit deposit field for unpaid status.

## Invoice Details

### PDF Changes

**Client PDF** now shows:
- Subtotal
- GST (if applicable)
- **Grand Total**
- **Deposit Paid** (if > 0)
- **Balance Due** (if > 0)
- **Payment Status** (PAID/PARTIAL/UNPAID) with color coding

**Internal PDF** additionally shows:
- Total Cost
- Total Profit
- All payment details

### Payment Status

- **PAID**: Balance due = $0.00 (deposit equals grand total)
- **PARTIAL**: Deposit paid but balance remains
- **UNPAID**: No deposit paid (balance = grand total)

## P/L Report Updates

### Daily Report Example

```
📊 Daily P/L Report
📅 Date: 2026-01-23

📝 Total Invoices: 5

💵 Total Revenue: $1,234.56
💸 Amount Received: $450.00
📅 Outstanding: $784.56

💰 Total Cost: $789.00
📈 Total Profit: $445.56
📊 Total GST: $50.00

📄 Payment Status:
  ✅ Paid: 1
  🔶 Partial: 3
  ⏳ Unpaid: 1

📊 Profit Margin: 36.1%
```

### Key Metrics

- **Total Revenue**: Sum of all grand totals (what clients owe)
- **Amount Received**: Sum of all deposits paid (actual cash received)
- **Outstanding**: Total balance due across all invoices
- **Payment Status**: Breakdown by payment state

## MongoDB Setup

### Configuration

Add to your `.env`:

```env
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DATABASE=telegram_bot
```

### Database Structure

**Collection**: `invoices`

**Document Schema**:
```json
{
  "_id": ObjectId,
  "invoice_number": "INV-20260123-1234",
  "date": "January 23, 2026",
  "timestamp": ISODate("2026-01-23T19:00:00Z"),
  "chat_id": 12345,
  "customer_name": "John Doe",
  "subtotal": 540.00,
  "gst": 48.60,
  "grand_total": 588.60,
  "deposit_paid": 150.00,
  "balance_due": 438.60,
  "payment_status": "PARTIAL",
  "total_cost": 215.00,
  "total_profit": 325.00,
  "items_count": 3,
  "items": [...]
}
```

### Indexes

The following indexes are automatically created:
- `chat_id`: For filtering by user
- `timestamp`: For date range queries
- `chat_id + timestamp`: Compound index for efficient reporting

## Testing

### Test Deposit Functionality

```bash
uv run python test_invoices.py
```

Generates sample PDFs with:
1. Invoice with $150 deposit (PARTIAL status)
2. Invoice with no deposit (UNPAID status)

### Test MongoDB Connection

```bash
uv run python test_mongo.py
```

Tests:
- MongoDB connectivity
- Invoice storage
- Summary calculations
- Payment status tracking

## Migration from JSON to MongoDB

If you were using JSON file storage:

1. **Set MongoDB URI** in `.env`
2. **Restart the bot** - it will automatically use MongoDB
3. **Old JSON data** remains in `invoices/invoice_records.json` as backup
4. **New invoices** will be stored in MongoDB

To migrate old data (optional):
```python
from pathlib import Path
import json
from src.mongo_storage import MongoInvoiceStorage

# Load old JSON data
with open("invoices/invoice_records.json") as f:
    old_data = json.load(f)

# Connect to MongoDB
storage = MongoInvoiceStorage("your-uri", "telegram_bot")

# Insert old records
for record in old_data:
    storage.invoices.insert_one(record)
```

## Troubleshooting

### MongoDB Connection Issues

**Error**: `ServerSelectionTimeoutError`
- Check network connectivity
- Verify MongoDB URI is correct
- Ensure IP whitelist includes your server

**Fallback**: Bot automatically uses JSON storage if MongoDB fails

### Payment Status Not Showing

- Ensure you're using the latest code
- Check that `deposit_paid` field exists in stored invoices
- Old invoices may need `payment_status` field added

### Reports Show $0 Received

- This is correct if all invoices have no deposits
- Add `Deposit: <amount>` to invoice messages to track payments

## Benefits

### For You
- **Track cash flow**: See actual money received vs billed
- **Payment reminders**: Know which invoices need follow-up
- **Persistent data**: Never lose invoice history
- **Better insights**: Understand payment patterns

### For Clients
- **Clear payment terms**: See deposit and balance on invoice
- **Payment status**: Know what's been paid and what's owed
- **Professional invoices**: Color-coded payment indicators

## Next Steps

1. **Test with real invoices** using deposits
2. **Check MongoDB dashboard** to see stored data
3. **Review daily/weekly reports** for payment insights
4. **Share PDFs** with sample deposit invoicing to clients
