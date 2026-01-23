# Automated Reports Feature

## Overview

The bot now includes automated daily and weekly P/L reports based on invoices generated in your chat.

## Features

### 1. Daily Reports
- **Automatic**: Sent every day at 7:00 PM SGT
- **Manual**: Use `/daily` command anytime
- **Includes**:
  - Total invoices generated today
  - Total revenue
  - Total cost
  - Total profit
  - Total GST collected
  - Profit margin percentage

### 2. Weekly Reports
- **Automatic**: Sent every Friday at 7:00 PM SGT
- **Manual**: Use `/weekly` command anytime
- **Period**: Last 7 days (Friday 7pm to Friday 7pm)
- **Includes**:
  - All daily report metrics
  - Average invoice value

## Setup

### Step 1: Get Your Chat ID

You need your Telegram chat ID for automated reports.

**Option A: Use the bot command**
```
/chatid
```

**Option B: Use the helper script**
```bash
# Send /start to your bot first, then run:
uv run python scripts/get_chat_id.py
```

### Step 2: Configure Chat ID

Add your chat ID to `.env`:
```env
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Step 3: Restart the Bot

```bash
uv run python -m src.bot
```

## Commands

- `/start` - Welcome message with feature overview
- `/help` - Invoice format help
- `/chatid` - Get your chat ID for automated reports
- `/daily` - Get today's P/L summary
- `/weekly` - Get this week's P/L summary

## Data Storage

Invoice records are stored in JSON format at:
```
invoices/invoice_records.json
```

Each record includes:
- Invoice number and date
- Customer name
- Subtotal, GST, and grand total
- Cost and profit
- Number of items
- Timestamp

## Timezone

All scheduled reports use Singapore Time (SGT / Asia/Singapore timezone).

## Example Reports

### Daily Report
```
📊 Daily P/L Report
📅 Date: 2026-01-23

📝 Total Invoices: 5

💵 Total Revenue: $1,234.56
💰 Total Cost: $789.00
📈 Total Profit: $445.56
📊 Total GST: $50.00

📊 Profit Margin: 36.1%
```

### Weekly Report
```
📊 Weekly P/L Report
📅 Period: 2026-01-16 to 2026-01-23

📝 Total Invoices: 23

💵 Total Revenue: $5,678.90
💰 Total Cost: $3,456.00
📈 Total Profit: $2,222.90
📊 Total GST: $234.00

📊 Profit Margin: 39.1%
📊 Average Invoice Value: $246.91
```

## Troubleshooting

### Reports not being sent automatically

1. Check that `TELEGRAM_CHAT_ID` is set in `.env`
2. Restart the bot after setting the chat ID
3. Check bot logs for any errors

### Wrong timezone

Make sure your system has the correct timezone data. The bot uses `zoneinfo` which requires:
- Python 3.9+ (built-in)
- Timezone database (usually included with OS)

### Testing scheduled reports

You can test the report format without waiting for the scheduled time by using:
- `/daily` - Test daily report format
- `/weekly` - Test weekly report format
