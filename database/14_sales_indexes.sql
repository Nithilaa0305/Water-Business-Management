-- 14: indexes for the selling side
CREATE INDEX idx_sales_customer ON sales(customer_id);
CREATE INDEX idx_sales_date ON sales(sale_date);
CREATE INDEX idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX idx_sale_items_batch ON sale_items(batch_id);
CREATE INDEX idx_sale_returns_sale ON sale_returns(sale_id);
CREATE INDEX idx_ledger_customer_time ON customer_ledger(customer_id, entry_time);
CREATE INDEX idx_payments_customer ON payments(customer_id);
CREATE INDEX idx_payments_date ON payments(payment_date);
CREATE INDEX idx_container_movements_customer ON container_movements(customer_id);
CREATE INDEX idx_expenses_date ON expenses(expense_date);
CREATE INDEX idx_supplier_payments_supplier ON supplier_payments(supplier_id);
