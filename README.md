# Telegram Invoice Bot

A Telegram bot that generates professional PDF invoices from simple text messages with automated daily and weekly P/L reports. Built with Python, Pydantic for type safety, and ReportLab for PDF generation.

## Features

- 📄 Generate PDF invoices from forwarded messages (client & internal versions)
- 💰 Automatic GST calculation (applies when total ≥ $400)
- 📊 Track cost price, sale price, and profit margins
- 📈 Automated daily reports at 7 PM SGT
- 📅 Automated weekly reports every Friday at 7 PM SGT
- 🔍 Manual P/L summaries with `/daily` and `/weekly` commands
- ✅ Type-safe with Pydantic models
- 🎨 Clean, formatted with Ruff

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

## Installation

1. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository**
   ```bash
   cd telegram-bot-accounting
   ```

3. **Install dependencies with uv**
   ```bash
   uv sync
   ```

4. **Install development dependencies (optional)**
   ```bash
   uv sync --all-extras
   ```

## Configuration

1. **Create a `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and configure**:
   ```env
   # Get token from @BotFather on Telegram
   TELEGRAM_BOT_TOKEN=your_bot_token_here

   # Your chat ID for automated reports (get it with /chatid command)
   TELEGRAM_CHAT_ID=

   # Your business details
   BUSINESS_NAME=Your Business Name
   BUSINESS_ADDRESS=123 Business Street, City
   BUSINESS_PHONE=+65 1234 5678
   BUSINESS_EMAIL=contact@yourbusiness.com
   BUSINESS_REGISTRATION=ROC123456  # Optional

   # GST Configuration (9% in Singapore)
   GST_RATE=0.09
   GST_THRESHOLD=400.00
   ```

3. **Get your Telegram Bot Token**:
   - Open Telegram and search for [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow the instructions
   - Copy the token and paste it in your `.env` file

4. **Get your Chat ID** (for automated reports):
   - Start your bot with `/start`
   - Send `/chatid` to the bot
   - Copy the chat ID and add it to your `.env` file
   - Restart the bot to enable automated reports

## Usage

### Running the Bot

```bash
uv run python -m src.bot
```

Or directly:
```bash
uv run python src/bot.py
```

### Message Format

Send messages to your bot in this format:

```
Customer: John Doe
---
Item Name | Cost Price | Sale Price | Quantity
Laptop Case | 15 | 25 | 1
USB Cable | 2.50 | 5 | 3
Mouse Pad | 3 | 8 | 2
---
```

**Simplified format** (without headers):
```
Customer: Jane Smith
---
Laptop Case | 15 | 25 | 1
USB Cable | 2.50 | 5 | 3
Mouse Pad | 3 | 8 | 2
```

**Without customer** (optional):
```
Laptop Case | 15 | 25 | 1
USB Cable | 2.50 | 5 | 3
```

### Bot Commands

- `/start` - Welcome message and feature overview
- `/help` - Show invoice format instructions and examples
- `/chatid` - Get your chat ID for automated reports
- `/daily` - Get today's P/L summary (manual trigger)
- `/weekly` - Get this week's P/L summary (manual trigger)

### Automated Reports

The bot automatically sends:
- **Daily report** at 7:00 PM SGT with the day's P/L
- **Weekly report** every Friday at 7:00 PM SGT with the week's P/L

See [REPORTS.md](REPORTS.md) for detailed documentation on reports.

### How It Works

1. Send a message with items in the format above
2. Bot parses the message and validates data with Pydantic
3. Calculates totals, costs, and profits
4. Applies GST if subtotal ≥ threshold
5. Generates two professional PDF invoices:
   - **Client PDF**: For customers (no cost prices or profit)
   - **Internal PDF**: For your records (includes cost & profit)
6. Sends both PDFs back to you
7. Stores invoice data for reports

## Invoice Details

The generated PDFs include:
- Business logo (if provided in `assets/logo.jpg`)
- Business information (address, phone, email)
- Invoice number and date
- Customer name (if provided)
- Itemized list with prices
- Subtotal, GST (if applicable), and grand total
- Total cost and profit breakdown (internal PDF only)

## Development

### Format Code with Ruff

```bash
uv run ruff format .
```

### Lint Code

```bash
uv run ruff check .
```

### Fix Linting Issues

```bash
uv run ruff check --fix .
```

### Add New Dependencies

```
telegram-bot-accounting/
├── src/
│   ├── __init__.py           # Package init
│   ├── bot.py                # Main bot logic
│   ├── config.py             # Pydantic settings
│   ├── models.py             # Pydantic data models
│   ├── parser.py             # Message parser
│   └── pdf_generator.py      # PDF generation
├── invoices/                 # Generated PDFs (auto-created)
├── .venv/                    # Virtual environment (uv managed)
├── .env                      # Environment variables (not in git)
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── pyproject.toml            # Project config & dependencies (uv)
├── uv.lock                   # Dependency lock file (uv)
└── README.md                 # This file
``` ├── __init__.py           # Package init
│   ├── bot.py                # Main bot logic
│   ├── config.py             # Pydantic settings
│   ├── models.py             # Pydantic data models
│   ├── parser.py             # Message parser
│   └── pdf_generator.py      # PDF generation
├── invoices/                 # Generated PDFs (auto-created)
├── .env                      # Environment variables (not in git)
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── pyproject.toml            # Project config & dependencies
└── README.md                 # This file
```

## GST Calculation

- GST is applied only when the **subtotal ≥ threshold** (default: $400)
- Default GST rate: 9% (configurable in `.env`)
- Formula: `Grand Total = Subtotal + (Subtotal × GST Rate)`

## Troubleshooting

**Bot doesn't start:**
- Check that `TELEGRAM_BOT_TOKEN` is set correctly in `.env`
- Verify the token with @BotFather

**Parse errors:**
- Ensure items are separated by pipe (`|`) characters
- Check that prices and quantities are valid numbers
- Use `/help` in the bot to see format examples

**PDF generation fails:**
- Check that the `invoices/` directory can be created
- Ensure sufficient disk space

## License

ISC

## Support

For issues or questions, please open an issue on GitHub.
Accounting bot for Telegram Biz
