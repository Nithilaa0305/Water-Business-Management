# Accounting & Financial Calculation Rules

## 1. Exact Decimal Financial Representation
All monetary values in Water Business Manager are calculated and stored internally as exact integer minor currency units (cents in Sri Lankan Rupees, where Rs. 1.00 = 100 cents). Binary floating-point representation (`float`) is strictly prohibited in the financial calculation service layer to eliminate IEEE 754 rounding artifacts.

## 2. First-In, First-Out (FIFO) Inventory Costing
- Inventory batches are prioritized strictly by `received_date ASC, id ASC`.
- When an invoice item is sold, quantity is deducted from the oldest active batch first.
- If an order spans multiple batches, each slice retains its exact historical cost.
- Historical purchase costs remain completely immutable. A subsequent price change on products or new supplier batches never alters completed invoice COGS or past gross profit.

### Example:
- Batch A: 40 bottles @ Rs. 100 cost
- Batch B: 60 bottles @ Rs. 120 cost
- Sale of 60 bottles @ Rs. 150 selling price:
  - 40 bottles from Batch A (Cost = 40 × 100 = Rs. 4,000)
  - 20 bottles from Batch B (Cost = 20 × 120 = Rs. 2,400)
  - Total COGS = Rs. 6,400
  - Net Sales Revenue = 60 × 150 = Rs. 9,000
  - Gross Profit = 9,000 − 6,400 = Rs. 2,600

## 3. Revenue vs Collections
- **Net Sales Revenue**:
  $$\text{Net Sales Revenue} = \text{Gross Sales} - \text{Discounts} + \text{Delivery Charges}$$
- **Credit Collections**: Collections of past credit sales (receiving customer payments) are cash inflows that settle accounts receivable. They are **never** counted as new sales revenue.
- **Refundable Bottle Deposits**: Deposits collected for reusable 19L containers are recorded as **Customer Liabilities**, never as sales revenue or business profit. When refunded, liability and cash decrease equally with zero profit/loss impact.

## 4. Profit & Loss Formulas
1. **Gross Profit**:
   $$\text{Gross Profit} = \text{Net Sales Revenue} - \text{Cost of Goods Sold (FIFO)}$$
2. **Net Operating Profit**:
   $$\text{Net Operating Profit} = \text{Gross Profit} - \text{Operating Expenses}$$

## 5. Cashbook Reconciliation
The Cashbook distinguishes between economic profitability and cash liquidity:
- **Cash Inflows**:
  - Cash collected on walk-in sales
  - Customer payments received for credit invoices
  - Refundable bottle deposits collected
- **Cash Outflows**:
  - Cash paid to suppliers
  - Operating expenses paid in cash
  - Bottle deposits refunded to customers
- **Net Cash Movement**:
  $$\text{Net Cash Flow} = \sum \text{Inflows} - \sum \text{Outflows}$$
