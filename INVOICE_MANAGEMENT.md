# Invoice Management Features

This document describes the new invoice management commands for tracking and updating payments.

## Features Overview

The bot now includes three powerful commands for managing invoices:

1. **Inception Report** (`/inception`) - All-time P/L summary
2. **Partial Invoices** (`/partial`) - List invoices with outstanding balances
3. **Payment Updates** (`/payment`) - Update deposit amounts on existing invoices

## Commands

### 1. Inception Report (`/inception`)

Get a complete P/L summary from the beginning of time (all invoices ever created).

**Usage:**
```
/inception
```

**Example Output:**
```
📊 Inception P/L Report
📅 All-Time Summary

📝 Total Invoices: 47
💵 Total Revenue: $12,450.00
💸 Amount Received: $9,200.00
📅 Outstanding: $3,250.00

💰 Total Cost: $6,800.00
📈 Total Profit: $5,650.00
📊 Total GST: $980.00

📄 Payment Status:
  ✅ Paid: 32
  🔶 Partial: 10
  ⏳ Unpaid: 5

📊 Profit Margin: 45.4%
📊 Average Invoice Value: $264.89
```

**When to use:**
- Review overall business performance
- Calculate total revenue and profit since inception
- Track payment collection rates
- Analyze profit margins over time

---

### 2. Partial Invoices (`/partial`)

List all invoices that have partial payments (where customers have paid some but not all of the invoice amount).

**Usage:**
```
/partial
```

**Example Output:**
```
📋 Partial Payment Invoices

Found 3 invoice(s) with partial payments:

🔸 Invoice: INV-042
  👤 Customer: John Doe
  📅 Date: 2024-01-28
  💵 Grand Total: $850.00
  💸 Paid: $400.00
  📅 Balance Due: $450.00

🔸 Invoice: INV-038
  👤 Customer: Jane Smith
  📅 Date: 2024-01-25
  💵 Grand Total: $1,200.00
  💸 Paid: $600.00
  📅 Balance Due: $600.00

🔸 Invoice: INV-035
  👤 Customer: Bob Johnson
  📅 Date: 2024-01-22
  💵 Grand Total: $320.00
  💸 Paid: $100.00
  📅 Balance Due: $220.00
```

**When to use:**
- Track outstanding payments from customers
- Follow up on partial payments
- Review which invoices need payment reminders
- Monitor cash flow and collections

---

### 3. Update Payment (`/payment`)

Update the deposit amount on an existing invoice. The bot automatically recalculates the balance due and payment status.

**Usage:**
```
/payment <invoice_number> <new_deposit_amount>
```

**Parameters:**
- `invoice_number`: The invoice ID (e.g., INV-042)
- `new_deposit_amount`: The total amount paid so far (not additional payment)

**Examples:**

**Add initial payment:**
```
/payment INV-042 250.00
```
Output:
```
✅ Successfully updated payment for invoice INV-042
New deposit amount: $250.00
```

**Update to full payment:**
```
/payment INV-042 850.00
```
Output:
```
✅ Successfully updated payment for invoice INV-042
New deposit amount: $850.00
```

**Invoice not found:**
```
/payment INV-999 100.00
```
Output:
```
❌ Invoice INV-999 not found.
Please check the invoice number and try again.
```

**Invalid amount:**
```
/payment INV-042 abc
```
Output:
```
Invalid deposit amount. Please provide a valid number.
Example: /payment INV-001 500.00
```

**Payment Status Changes:**
- If `deposit >= grand_total`: Status becomes **PAID** ✅
- If `deposit > 0` but `< grand_total`: Status becomes **PARTIAL** 🔶
- If `deposit = 0`: Status becomes **UNPAID** ⏳

---

## Workflow Examples

### Scenario 1: Following Up on Partial Payments

1. Check which invoices need follow-up:
   ```
   /partial
   ```

2. Customer pays additional amount, update the invoice:
   ```
   /payment INV-042 650.00
   ```

3. Verify the invoice is no longer in partial list:
   ```
   /partial
   ```

### Scenario 2: End-of-Month Reconciliation

1. Get overall performance:
   ```
   /inception
   ```

2. Review outstanding invoices:
   ```
   /partial
   ```

3. Update payments as they come in:
   ```
   /payment INV-038 1200.00
   /payment INV-035 320.00
   ```

4. Check updated metrics:
   ```
   /inception
   ```

### Scenario 3: Converting Unpaid to Partial

When a customer makes their first payment on an unpaid invoice:

```
/payment INV-050 200.00
```

The invoice automatically moves from UNPAID to PARTIAL status.

---

## Payment Status Indicators

All reports show payment status counts:

- **✅ PAID**: Full payment received (`deposit >= grand_total`)
- **🔶 PARTIAL**: Some payment received (`0 < deposit < grand_total`)
- **⏳ UNPAID**: No payment received (`deposit = 0`)

---

## Tips & Best Practices

1. **Use inception report weekly** to track overall business health
2. **Check partial invoices daily** to follow up on outstanding payments
3. **Update payments immediately** when customers pay to keep records accurate
4. **Note the deposit amount is total paid**, not an additional payment
5. **Keep invoice numbers handy** for quick payment updates

---

## Integration with Reports

These features integrate seamlessly with existing reports:

- **Daily Report** (`/daily`): Shows today's payment status breakdown
- **Weekly Report** (`/weekly`): Shows this week's payment status breakdown
- **Inception Report** (`/inception`): Shows all-time payment status breakdown

All reports include:
- Amount Received (total deposits)
- Outstanding (total balance due)
- Payment status counts

---

## Storage

All payment updates are stored in:
- **MongoDB** (if configured) - Primary storage with persistence
- **JSON file** (fallback) - Local storage for development

Data persists between bot restarts and deployments.

---

## Error Handling

The bot handles common errors gracefully:

- **Invoice not found**: Checks if invoice number exists before updating
- **Invalid amounts**: Validates numeric input and rejects negative values
- **Missing parameters**: Provides helpful usage examples
- **Database errors**: Logs errors and informs user of failure

---

## Future Enhancements

Potential future additions:
- Export partial invoices to CSV
- Send payment reminders automatically
- Track payment history per invoice
- Generate aging reports (30/60/90 days)
- Filter partial invoices by date range or customer

---

For more information on the deposit feature and payment tracking, see [DEPOSIT_FEATURE.md](DEPOSIT_FEATURE.md).
