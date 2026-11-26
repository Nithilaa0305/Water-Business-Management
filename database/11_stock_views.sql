-- 11: screens and reports for stock, activity and prices

-- which batch is current, which is next
CREATE VIEW v_batch_queue AS
SELECT b.batch_id, b.batch_number, b.type_id,
       p.product_name || ' - ' || t.type_name AS item,
       b.received_date, b.current_quantity, b.buying_price, b.selling_price, b.expiry_date,
       ROW_NUMBER() OVER (PARTITION BY b.type_id ORDER BY b.received_date, b.created_at, b.batch_number) AS queue_position,
       CASE ROW_NUMBER() OVER (PARTITION BY b.type_id ORDER BY b.received_date, b.created_at, b.batch_number)
            WHEN 1 THEN 'Current' WHEN 2 THEN 'Next' ELSE 'Waiting' END AS batch_status
  FROM stock_batches b
  JOIN product_types t ON t.type_id = b.type_id
  JOIN products p ON p.product_id = t.product_id
 WHERE b.current_quantity > 0;

-- total stock for each type (a low-stock limit of 0 means "no alert")
CREATE VIEW v_stock_by_type AS
SELECT t.type_id, p.product_name, t.type_name,
       p.product_name || ' - ' || t.type_name AS item,
       u.unit_name,
       COALESCE(SUM(b.current_quantity), 0) AS total_quantity,
       COUNT(b.batch_id) FILTER (WHERE b.current_quantity > 0) AS batches_in_stock,
       (t.low_stock_limit > 0 AND COALESCE(SUM(b.current_quantity), 0) <= t.low_stock_limit) AS low_stock
  FROM product_types t
  JOIN products p ON p.product_id = t.product_id
  LEFT JOIN units u ON u.unit_id = t.unit_id
  LEFT JOIN stock_batches b ON b.type_id = t.type_id
 GROUP BY t.type_id, p.product_name, t.type_name, u.unit_name, t.low_stock_limit;

-- who did what, in time order
CREATE VIEW v_activity_timeline AS
SELECT a.action_time, a.action_time::date AS action_date,
       u.full_name AS person, u.user_role, a.action_type, a.description,
       a.reference_type, a.reference_id
  FROM activity_log a
  JOIN app_users u ON u.user_id = a.user_id
 ORDER BY a.action_time DESC;

-- who was signed in and when
CREATE VIEW v_user_sessions AS
SELECT s.session_id, u.full_name AS person, u.user_role,
       s.signed_in_at, s.signed_out_at, s.sign_out_reason,
       COALESCE(s.signed_out_at, clock_timestamp()) - s.signed_in_at AS duration
  FROM user_sessions s
  JOIN app_users u ON u.user_id = s.user_id
 ORDER BY s.signed_in_at DESC;

-- how buying and selling prices changed
CREATE VIEW v_price_history AS
SELECT h.changed_at, p.product_name || ' - ' || t.type_name AS item,
       h.price_kind, h.old_price, h.new_price,
       b.batch_number, u.full_name AS changed_by_person, h.note
  FROM price_history h
  JOIN product_types t ON t.type_id = h.type_id
  JOIN products p ON p.product_id = t.product_id
  LEFT JOIN stock_batches b ON b.batch_id = h.batch_id
  LEFT JOIN app_users u ON u.user_id = h.changed_by
 ORDER BY h.changed_at DESC;
