# New Features Summary

## What's New

Two major features have been added to your Telegram Invoice Bot:

### 1. Automated Daily Reports (7 PM SGT)
Every day at 7:00 PM Singapore Time, the bot will automatically send you a P/L summary including:
- Total number of invoices generated today
- Total revenue (grand total of all invoices)
- Total cost (sum of all cost prices)
- Total profit (revenue - cost)
- Total GST collected
- Profit margin percentage

**Manual Trigger**: Use `/daily` command anytime to get today's summary.

### 2. Automated Weekly Reports (Friday 7 PM SGT)
Every Friday at 7:00 PM Singapore Time, the bot will send a weekly P/L summary covering the past 7 days (Friday to Friday) including:
- All daily report metrics
- Average invoice value

**Manual Trigger**: Use `/weekly` command anytime to get this week's summary.

## How It Works

1. **Invoice Storage**: Every time you generate an invoice, the bot now stores the data in `invoices/invoice_records.json`
2. **Scheduled Jobs**: The bot uses python-telegram-bot's job queue to schedule reports at specific times
3. **Singapore Timezone**: All schedules use `Asia/Singapore` timezone (SGT)

## Setup Required

### Get Your Chat ID

You need to configure your Telegram chat ID for automated reports:

**Option 1: Use bot command**
```
1. Send /start to your bot
2. Send /chatid
3. Copy the chat ID shown
```

**Option 2: Use helper script**
```bash
uv run python scripts/get_chat_id.py
```

### Configure Environment

Add your chat ID to `.env`:
```env
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Restart Bot

After setting the chat ID, restart the bot:
```bash
uv run python -m src.bot
```

## New Commands

- `/chatid` - Get your chat ID for automated reports
- `/daily` - Get today's P/L summary
- `/weekly` - Get this week's P/L summary

## Files Added/Modified

### New Files
- `src/storage.py` - Invoice data storage and retrieval
- `scripts/get_chat_id.py` - Helper to get your chat ID
- `REPORTS.md` - Detailed documentation on reports

### Modified Files
- `src/bot.py` - Added report commands and scheduled jobs
- `src/config.py` - Added `telegram_chat_id` setting
- `.env` - Added `TELEGRAM_CHAT_ID` field
- `README.md` - Updated with new features

### Data Files
- `invoices/invoice_records.json` - JSON storage for invoice records (created automatically)

## Example Report

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

## Testing

You can test the reports immediately without waiting for scheduled times:

1. Generate some invoices by sending messages to your bot
2. Run `/daily` to see today's summary
3. Run `/weekly` to see this week's summary

## Troubleshooting

### Reports not sending automatically
- Make sure `TELEGRAM_CHAT_ID` is set in `.env`
- Restart the bot after setting the chat ID
- Check bot logs for errors

### Wrong time for scheduled reports
- The bot uses Singapore Time (SGT/UTC+8)
- Scheduled times are: Daily at 7 PM, Weekly on Fridays at 7 PM

### Testing scheduled jobs
- You don't need to wait for the scheduled time
- Use `/daily` and `/weekly` commands to test the report format
- The bot must be running continuously for scheduled jobs to work

## Next Steps

1. Get your chat ID with `/chatid`
2. Add it to `.env`
3. Restart the bot
4. Generate some test invoices
5. Try `/daily` and `/weekly` commands
6. Wait for your first automated report at 7 PM SGT!
