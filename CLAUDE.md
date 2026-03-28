# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run bot locally (polling mode)
uv run python -m src.bot

# Lint / format
uv run ruff check .
uv run ruff format .

# Ad-hoc test scripts (not a test suite — run directly)
uv run python test_invoices.py
uv run python test_storage.py
uv run python test_mongo.py
uv run python test_new_commands.py
```

## Architecture

Two Telegram bots share a single codebase, deployed as a Vercel serverless function (`api/webhook.py`) that routes updates to the correct bot based on the incoming webhook path.

**Invoice Bot** (`src/bot.py`) — private bot for business accounting:
- Parses freeform Telegram messages into invoices via `src/parser.py`
- Generates dual PDFs (client copy + internal with cost breakdown) via `src/pdf_generator.py` (ReportLab)
- Calculates GST at 9% when subtotal ≥ $400 AUD (configurable)
- Schedules daily (7 PM SGT) and weekly (Friday 7 PM SGT) P/L reports
- Tracks card inventory with `/buycard` / `/sellcard` / `/cards`

**Catalogue Bot** (`src/catalogue_bot.py`) — public-facing customer search bot:
- Auto-indexes messages (text + photo captions) from designated group chats
- Serves full-text search results with links back to original Telegram posts
- Detects listing status (available / reserved / sold) from message keywords
- Logs search queries for owner analytics

**Storage layer** — two modes selected at runtime:
- **Local/dev**: JSON files in `./invoices/` (`src/storage.py`)
- **Production**: MongoDB (`src/mongo_storage.py` for invoices/cards, `src/catalogue_storage.py` for catalogue listings)

`src/config.py` uses Pydantic Settings to load all env vars. `src/models.py` defines `InvoiceData`, `InvoiceItem`, `InvoiceTotals`, and `CardPurchase`.

## Deployment

Hosted on Vercel. `api/webhook.py` is the single entry point — it instantiates both bot applications and dispatches to them by path (`/api/webhook` → invoice bot, `/api/catalogue_webhook` → catalogue bot). Both bots must have their webhooks registered to their respective URLs.

## Environment Variables

Copy `.env.example` to `.env`. Key variables:

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Invoice bot token |
| `CATALOGUE_BOT_TOKEN` | Catalogue bot token |
| `MONGODB_URI` | MongoDB connection (omit to use JSON storage) |
| `TELEGRAM_CHAT_ID` | Chat ID for automated P/L reports |
| `OWNER_CHAT_ID` / `OWNER_USERNAME` | Catalogue bot owner for search notifications |
| `CATALOGUE_GROUP_IDS` | Comma-separated group IDs for the catalogue indexer |
| `GST_RATE` / `GST_THRESHOLD` | GST configuration (default: 0.09 / 400.00) |
| `BUSINESS_NAME` / `BUSINESS_ADDRESS` / … | Invoice header details |
