# Water Business Manager
### Complete Bottled Water Stock, Billing, Credit, Refill and Revenue Management System

A production-ready Windows desktop application built specifically for small bottled water wholesale and distribution businesses in Sri Lanka.

---

## Key Features

1. **Product Inventory & Multi-Packaging**:
   - Built-in support for standard sizes: 500 ml, 1 L, 1.5 L, 5 L, and 19 L returnable bottles.
   - Base bottle inventory with packaging conversion (e.g. Case of 12, Case of 24).
2. **Traceable FIFO Batch Management**:
   - Automatically generates unique sequential batch numbers.
   - Strict First-In, First-Out (FIFO) allocation ensuring historical unit cost integrity.
3. **High-Speed Billing & Invoicing**:
   - Walk-in cash or identified customer credit sales.
   - Intelligent customer price suggestions based on agreed contracts and sales history.
   - Automatic 19L bottle exchange tracking on each invoice.
4. **Special 19 L Returnable Bottle Workflow**:
   - 7 distinct physical bottle states tracked continuously.
   - Full bottle delivery, exchange, and empty return without water purchase.
   - Refill batch workflow tracking water treatment, caps, and direct labour costs.
   - Physical container balance reconciliation.
5. **Customer Accounts & Credit Management**:
   - Real-time customer financial ledger.
   - Automatic payment allocation to oldest invoices.
   - Overpayment handled securely as customer advance credits.
   - Overdue aging analysis (Current, 1–30, 31–60, >60 days).
6. **Financial Reports & Analytics**:
   - Profit & Loss statements with exact FIFO COGS.
   - Cashbook distinguishing cash sales, credit collections, deposits, and expenses.
7. **Bilingual Localization (English & தமிழ்)**:
   - Full interface and printable invoice localization with complex Tamil Unicode support.
8. **Data Safety & Excel Integration**:
   - Stored in `%LOCALAPPDATA%\WaterBusinessManager\data\business.db`.
   - Transactional online SQLite backups and safe restores.
   - OpenPyXL Excel export and template-based master data import.

---

## Technology Stack
- **Python 3.13 / PySide6** (Qt Widgets)
- **SQLite 3** (WAL mode with foreign keys strictly enforced)
- **SQLAlchemy 2.x**
- **openpyxl** (Excel import/export)
- **argon2-cffi** & salted SHA-256 for secure credential hashing
- **PyInstaller & Inno Setup** for packaging

---

## Quick Start (Development)
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run tests
pytest -v

# Start application
python main.py
```

---

## Documentation
- [User Manual](docs/user_guide.md)
- [Database Architecture](docs/database_design.md)
- [Accounting & Costing Rules](docs/accounting_rules.md)
- [Build & Packaging Guide](docs/build_guide.md)
- [Automated QA Test Report](docs/test_report.md)
