# Wholesale Water Billing & Stock Management System
### Complete Bottled Water Stock, Billing, Credit, Refill, Revenue & Accounting System

A production-grade system built specifically for bottled water wholesale and distribution businesses in Sri Lanka.
This project integrates:
1. **Windows Desktop Application**: Built with Python 3.13, PySide6 (Qt6), SQLAlchemy, and SQLite.
2. **PostgreSQL Relational Database**: Complete schema in `database/` with 20 modular SQL scripts, views, triggers, and functions (`install.sql`).
3. **Web / API Backend**: Node/Express and FastAPI services with bilingual (English & தமிழ்) invoice generation and offline-ready sync.

---

## 1. Relational Database Modules (`database/`)
The system database is organized into 20 numbered modules for installation and verification:
- `00_extension.sql`: Extensions (UUID generation, pgcrypto).
- `01_lists.sql`: Units, categories, areas, payment methods, expense categories.
- `02_users_and_activity.sql`: User authentication, roles (`owner`, `manager`, `employee`), sessions, immutable activity log.
- `03_user_functions.sql`: User management, PIN hashing, login session verification.
- `04_products.sql`: Master products catalog and product types (SKUs, packaging, returnable flag).
- `05_customers_suppliers.sql`: Customer accounts (credit limits, balances, areas) and suppliers.
- `06_stock_tables.sql`: Batch-wise inventory (`stock_batches`), transaction history (`inventory_transactions`), and `price_history`.
- `07_stock_indexes.sql`: Performance indexes for stock lookup and batch queues.
- `08_receive_stock.sql`: Receiving workflow and auto-batch number generation.
- `09_stock_corrections.sql`: Stock adjustment, damage, and expiry management.
- `10_pick_batches.sql`: FIFO batch allocation engine (`pick_batches`).
- `11_stock_views.sql`: Batch queue (`v_batch_queue`), stock by type (`v_stock_by_type`), activity timeline.
- `12_customer_groups.sql`: Customer groups (`Regular`, `New`) and batch assignment rules.
- `13_sales_tables.sql`: Sales orders (`sales`), line items (`sale_items`), returns (`sale_returns`), ledger (`customer_ledger`), containers (`customer_containers`), and expenses.
- `14_sales_indexes.sql`: Sales performance indexes.
- `15_customer_accounts.sql`: Customer ledger functions, debt payment allocations.
- `16_create_sale.sql`: Atomic sale transaction with FIFO stock deduction and returnable can tracking.
- `17_cancel_and_return.sql`: Reversals, returns, and invoice cancellations.
- `18_containers_expenses_suppliers.sql`: 19L can exchange movements, operating expenses, and supplier payables.
- `19_reports.sql`: Reconciled statements, customer balances (`v_customer_balances`), and monthly P&L (`v_monthly_summary`).

---

## 2. Desktop Application Features (`app/`)
1. **Product Inventory & Multi-Packaging**:
   - Standard bottle sizes: 500 ml, 1 L, 1.5 L, 5 L, and 19 L returnable bottles.
   - Conversion between single bottles, packs, and cases (e.g. Case of 12, Case of 24).
2. **Traceable FIFO Batch Costing**:
   - Automatic generation of unique sequential batch numbers (`B-000001` format).
   - Strict First-In, First-Out (FIFO) allocation ensuring historical unit cost integrity.
3. **High-Speed Billing & Invoicing**:
   - Walk-in cash or identified customer credit sales.
   - Pre-configured agreed customer selling prices and on-the-fly custom overrides.
   - Automatic 19L bottle exchange tracking on each invoice.
4. **Special 19 L Returnable Bottle Workflow**:
   - Distinct physical bottle states: Full in shop, empty in shop, held by customer, damaged, refilling.
   - Full bottle delivery, exchange, and empty return without water purchase.
   - Refill batch workflow tracking water treatment, caps, and direct costs.
5. **Customer Accounts & Credit Management**:
   - Real-time customer financial ledger with strict debit/credit tracking.
   - Automatic payment allocation to current or oldest outstanding invoices.
   - Overpayment securely held as customer advance credits.
6. **Financial Reports & Analytics**:
   - Profit & Loss statements with exact FIFO COGS.
   - Cashbook distinguishing cash sales, credit collections, deposits, and expenses.
7. **Bilingual Localization (English & தமிழ்)**:
   - Full interface and printable invoice localization with complex Tamil Unicode support.

---

## 3. Quick Start

### Windows Desktop Application (Python)
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run tests
pytest -v

# Start application
python main.py
```

### PostgreSQL Database Installation
```sh
createdb billing
psql -d billing -v ON_ERROR_STOP=1 -f install.sql
```
