# Database Architecture & Entity-Relationship Design

## 1. Storage Engine
- **Engine**: SQLite 3 with WAL (Write-Ahead Logging) mode and foreign keys strictly enforced (`PRAGMA foreign_keys = ON;`).
- **Location**: `%LOCALAPPDATA%\WaterBusinessManager\data\business.db` (overrideable via `WATER_DB_PATH` environment variable).
- **Integrity**: Verified on every startup and before/after backups using SQLite online backup API and `PRAGMA integrity_check`.

## 2. Normalized Tables Overview

### Core Configuration
- `users`: User credentials, Argon2/salted SHA-256 password/PIN hashes, roles (`OWNER`, `MANAGER`, `EMPLOYEE`), activity status.
- `business_profile`: Business branding, contact details, currency symbol (`Rs.`), invoice/receipt prefixes, language.
- `system_settings`: Key-value application configurations.

### Products & Inventory
- `products`: Product master (`W0500`, `W1000`, `W1500`, `W5000`, `W19000`), categories, sizes, UOM, min stock level, returnable flag.
- `packaging_units`: Conversion factors (e.g. Case of 12 = 12 bottles, Case of 24 = 24 bottles).
- `inventory_batches`: Individual delivery/production batches with unique batch numbers, original quantity, remaining quantity, unit cost in cents, and status.
- `stock_movements`: Immutable stock ledger tracking every addition, sale, refill, return, and adjustment.
- `stock_adjustments`: Audit record of inventory adjustments with mandatory reason.

### Customers & Pricing
- `customers`: Customer master data, contact details, delivery routes, credit limits, opening balances.
- `customer_prices`: Customer-specific negotiated selling price agreements.
- `delivery_routes`: Geographic delivery routes.

### Sales & Invoicing
- `sales_invoices`: Posted and draft bills, customer link, invoice totals, discounts, payments, 19L delivered & returned counts.
- `sales_invoice_items`: Line items with ordered quantity, base bottle quantity, unit price, line discounts, and COGS.
- `sale_batch_allocations`: Exact FIFO allocations linking each invoice item to the specific batches deducted.

### Payments & Accounts Receivable
- `customer_payments`: Receipts from customers, payment method, unallocated advance balances.
- `customer_payment_allocations`: Junction table allocating payments against specific invoices.
- `customer_ledger`: Auditable running balance ledger (debits for invoices, credits for payments and credit notes).

### 19 L Returnable Containers
- `bottle_inventory`: Snapshot quantities across all 7 physical states:
  1. `FULL_AVAILABLE`
  2. `EMPTY_AVAILABLE`
  3. `IN_CLEANING_REFILL`
  4. `HELD_BY_CUSTOMERS`
  5. `DAMAGED`
  6. `LOST_WRITTEN_OFF`
  7. `PERMANENTLY_SOLD`
- `customer_bottle_ledger`: Independent bottle obligation ledger per customer (`running_balance = opening + issued - returned`).
- `bottle_movements`: Movement trail between physical states.
- `refill_batches`: 19L cleaning and refilling runs, direct treatment/cleaning/cap costs, unit cost calculation, and batch creation.
- `bottle_deposits` & `bottle_deposit_transactions`: Customer refundable deposit liabilities.

### Purchases, Expenses & Auditing
- `suppliers`: Supplier master data and terms.
- `purchase_invoices` & `purchase_invoice_items`: Inbound inventory purchases.
- `supplier_payments` & `supplier_ledger`: Accounts payable tracking.
- `expenses` & `expense_categories`: Categorized business expenses.
- `audit_logs`: Append-only activity log recording user actions, reference numbers, and before/after values.
