-- 07: indexes for the stock side
CREATE INDEX idx_types_product ON product_types(product_id);
CREATE INDEX idx_customers_name ON customers(customer_name);
CREATE INDEX idx_batches_type_fifo ON stock_batches(type_id, received_date, created_at) WHERE current_quantity > 0;
CREATE INDEX idx_batches_expiry ON stock_batches(expiry_date);
CREATE INDEX idx_inventory_batch ON inventory_transactions(batch_id);
CREATE INDEX idx_inventory_date ON inventory_transactions(transaction_date);
CREATE INDEX idx_price_history_type ON price_history(type_id, changed_at);
CREATE INDEX idx_activity_time ON activity_log(action_time);
CREATE INDEX idx_activity_user ON activity_log(user_id, action_time);
CREATE INDEX idx_sessions_user ON user_sessions(user_id, signed_in_at);
