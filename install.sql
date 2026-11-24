-- Installs the whole database with psql (run from this folder):
--   createdb billing
--   psql -d billing -v ON_ERROR_STOP=1 -f install.sql
-- In pgAdmin, open and run the files in database/ one by one, in number order.
\i database/00_extension.sql
\i database/01_lists.sql
\i database/02_users_and_activity.sql
\i database/03_user_functions.sql
\i database/04_products.sql
\i database/05_customers_suppliers.sql
\i database/06_stock_tables.sql
\i database/07_stock_indexes.sql
\i database/08_receive_stock.sql
\i database/09_stock_corrections.sql
\i database/10_pick_batches.sql
\i database/11_stock_views.sql
\i database/12_customer_groups.sql
\i database/13_sales_tables.sql
\i database/14_sales_indexes.sql
\i database/15_customer_accounts.sql
\i database/16_create_sale.sql
\i database/17_cancel_and_return.sql
\i database/18_containers_expenses_suppliers.sql
\i database/19_reports.sql
\i database/20_operational_integrity.sql
