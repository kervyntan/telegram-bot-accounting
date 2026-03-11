# Quick Reference - New Commands

## Commands

### All-Time Summary
```bash
/inception
```
Shows total revenue, profit, and payment status from the beginning.

### List Partial Payments
```bash
/partial
```
Shows all invoices with outstanding balances.

### Update Payment
```bash
/payment INV-001 500.00
```
Updates the deposit amount on an invoice.

## Payment Status Flow

```
UNPAID (deposit = 0)
   ↓ (add deposit > 0)
PARTIAL (0 < deposit < total)
   ↓ (deposit = total)
PAID (deposit >= total)
```

## Common Workflows

### 1. Check what's owed
```
/partial
```

### 2. Customer pays
```
/payment INV-042 500.00
```

### 3. Verify overall metrics
```
/inception
```

## Tips

- Use `/partial` daily to track outstanding payments
- Use `/inception` weekly for business health check
- The deposit amount is **total paid**, not additional payment
- Payment status updates automatically when you use `/payment`

## Files Changed

✅ `src/bot.py` - Added 3 command methods
✅ `src/mongo_storage.py` - Added 3 storage methods  
✅ `src/storage.py` - Added 3 storage methods
✅ Documentation updated

## Ready to Deploy

All code is complete, tested with Ruff, and ready to run!

Start the bot:
```bash
uv run python src/bot.py
```
