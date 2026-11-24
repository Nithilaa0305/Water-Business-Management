# Wholesale Billing Database

PostgreSQL database for a wholesale distributor's billing app: stock by batch, bills, regular-customer
accounts, returns, returnable containers, expenses, reports, and a locked record of who did what.

**Status:** version 1. The database was installed and tested by hand in pgAdmin (all expected numbers matched and all
rejection tests were blocked as designed). The application (screens) is not built yet.

## Requirements
- PostgreSQL 13 or newer (tested on 18)
- The `pgcrypto` extension (installed by `00_extension.sql`) for hashing PINs

## Install
Create a new, empty database first. Do not reuse another project's database.

**With psql**
```
createdb billing
psql -d billing -v ON_ERROR_STOP=1 -f install.sql
```

**With pgAdmin 4:** create the database, open the Query Tool on it, then open and run the files in `database/`
one by one, in number order (`00` to `19`). Each file ran successfully on its own during testing.

## What is in the folders
| File | What it builds |
|---|---|
| `00` to `03` | extension, editable lists, users, sessions, locked activity record, sign-in and role checks |
| `04` to `07` | products and their types, customers, suppliers, stock batches, stock ledger, price history, indexes |
| `08` to `11` | receive stock, correct stock, change prices, oldest-first picking, stock and activity views |
| `12` | customer groups and the batch rule, customer functions |
| `13` to `19` | bills, customer accounts, payments, returns, cancellations, containers, expenses, supplier payments, reports |
| `tests/` | sample data and checks. Use on a test database only |

## Main ideas
- **Product types:** a product (Drinking Water) has many types (500 ml, 19 L filled, case of 24). Stock is counted per type.
- **Batches:** every stock entry is a batch with its own buying price, selling price, date and quantity left.
- **Batch rule per customer group:** Regular customers are served from the oldest batch, New customers from the newest.
  A manager or the owner can choose a batch by hand. Groups and rules are editable in `customer_groups`.
- **Customer account:** every bill, payment, return and cancellation is a ledger entry with a running balance.
  Positive balance = the customer owes you; negative = you owe the customer.
- **Everything is done by functions:** the app calls a function, and stock, batches, the customer account and the
  activity record all change together in one transaction (all or nothing).
- **Activity record:** every action is logged with the person, time and description. Nobody can change or delete it.

## Functions the app calls
| Function | Who may use it |
|---|---|
| `sign_in`, `sign_out` | everyone |
| `create_user` | owner (the first user must be the owner) |
| `create_sale` (bill, optional payment at billing) | owner, manager, employee |
| `receive_payment`, `record_container_movement` | owner, manager, employee |
| `create_customer` | all (only manager/owner can set credit limit or group) |
| `set_customer_group`, `set_credit_limit` | owner, manager |
| `receive_stock`, `adjust_stock`, `set_batch_selling_price` | owner, manager |
| `cancel_sale`, `return_sale_item` | owner, manager |
| `record_expense`, `pay_supplier` | owner, manager |
| choosing a batch by hand in `create_sale`, going over a credit limit | owner, manager |

## Views for screens and reports
`v_stock_by_type`, `v_batch_queue`, `v_price_history`, `v_customer_balances`, `v_customer_statement`, `v_sales_list`,
`v_sale_item_details`, `v_customer_containers`, `v_supplier_balances`, `v_monthly_summary`, `v_profit_by_item`,
`v_profit_by_customer`, `v_daily_user_summary`, `v_today`, `v_activity_timeline`, `v_user_sessions`.

## Testing
On a test database: run `tests/test_part1.sql`, then `tests/test_part2.sql`, and compare with the expected results written
in the comments. `tests/test_rejections.sql` lists actions that must be refused; run them one at a time.

## Known limits (version 1)
- **Who may see costs and profit** is not enforced inside the database. Views are readable by any database login, so the
  app must hide buying prices and profit from employees.
- Sign-in uses a 4 to 8 digit PIN, and the automatic sign-out after inactivity is the app's job.
- Returned empty containers are tracked per customer but are not added back to your own stock.
- A bill-level discount is not split across items when something is returned.
- Customer groups are set by hand (no automatic promotion from New to Regular yet).
- There are no functions yet to change a PIN, deactivate a user, or edit product and customer details.
- Bills cannot be edited after saving. Corrections are made with a return or a cancellation.

## Security notes
- Never commit passwords, `.env` files or database dumps. `.gitignore` already excludes them.
- The sample users and PINs in `tests/` are for demonstration only.
- Before going live, create a dedicated database login for the app instead of using the `postgres` superuser.
- Keep regular backups, because everything lives on one device.

For an offline client installation, see [Windows handover checklist](WINDOWS-HANDOVER.md).
