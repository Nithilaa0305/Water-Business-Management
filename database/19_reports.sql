-- 19: screens and reports for customers, sales, profit and the owner
CREATE VIEW v_customer_balances AS
SELECT c.customer_id, c.customer_name, c.phone, a.area_name, g.group_name, c.credit_limit, c.balance,
       CASE WHEN c.balance > 0 THEN 'Customer owes you'
            WHEN c.balance < 0 THEN 'You owe customer'
            ELSE 'Settled' END AS balance_note,
       ABS(c.balance) AS amount,
       (c.credit_limit > 0 AND c.balance > c.credit_limit) AS over_limit
  FROM customers c
  LEFT JOIN areas a ON a.area_id = c.area_id
  LEFT JOIN customer_groups g ON g.group_id = c.group_id;

CREATE VIEW v_customer_statement AS
SELECT l.customer_id, c.customer_name, l.entry_time, l.entry_type, l.note,
       l.debit, l.credit, l.running_balance, u.full_name AS entered_by
  FROM customer_ledger l
  JOIN customers c ON c.customer_id = l.customer_id
  LEFT JOIN app_users u ON u.user_id = l.created_by
 ORDER BY c.customer_name, l.entry_time;

CREATE VIEW v_sales_list AS
SELECT s.sale_id, s.sale_number, s.sale_date, c.customer_name, g.group_name,
       s.subtotal, s.discount, s.total, s.amount_paid, s.total - s.amount_paid AS due,
       s.status, u.full_name AS made_by
  FROM sales s
  JOIN customers c ON c.customer_id = s.customer_id
  LEFT JOIN customer_groups g ON g.group_id = c.group_id
  JOIN app_users u ON u.user_id = s.created_by
 ORDER BY s.created_at DESC;

-- which batch went into which bill, at what price
CREATE VIEW v_sale_item_details AS
SELECT s.sale_number, s.sale_date, c.customer_name,
       p.product_name || ' - ' || t.type_name AS item,
       b.batch_number, i.quantity, i.unit_price, i.line_total,
       i.buying_price, i.returned_quantity, i.sale_item_id
  FROM sale_items i
  JOIN sales s ON s.sale_id = i.sale_id
  JOIN customers c ON c.customer_id = s.customer_id
  JOIN product_types t ON t.type_id = i.type_id
  JOIN products p ON p.product_id = t.product_id
  JOIN stock_batches b ON b.batch_id = i.batch_id
 ORDER BY s.created_at DESC, p.product_name, t.type_name;

CREATE VIEW v_customer_containers AS
SELECT cc.customer_id, c.customer_name, p.product_name || ' - ' || t.type_name AS container, cc.held
  FROM customer_containers cc
  JOIN customers c ON c.customer_id = cc.customer_id
  JOIN product_types t ON t.type_id = cc.type_id
  JOIN products p ON p.product_id = t.product_id;

CREATE VIEW v_supplier_balances AS
SELECT s.supplier_id, s.supplier_name,
       COALESCE(b.bought, 0) AS total_bought,
       COALESCE(p.paid, 0) AS total_paid,
       COALESCE(b.bought, 0) - COALESCE(p.paid, 0) AS you_owe
  FROM suppliers s
  LEFT JOIN (SELECT supplier_id, SUM(quantity_received * buying_price) AS bought
               FROM stock_batches GROUP BY supplier_id) b ON b.supplier_id = s.supplier_id
  LEFT JOIN (SELECT supplier_id, SUM(amount) AS paid
               FROM supplier_payments GROUP BY supplier_id) p ON p.supplier_id = s.supplier_id;

-- monthly summary: sales, cost, profit, expenses, cash collected
CREATE VIEW v_monthly_summary AS
WITH sales_m AS (
    SELECT to_char(sale_date, 'YYYY-MM') AS month, SUM(total) AS sales_total
      FROM sales WHERE status = 'completed' GROUP BY 1
), cogs_m AS (
    SELECT to_char(s.sale_date, 'YYYY-MM') AS month, SUM(i.quantity * i.buying_price) AS cost_of_goods
      FROM sale_items i JOIN sales s ON s.sale_id = i.sale_id
     WHERE s.status = 'completed' GROUP BY 1
), ret_m AS (
    SELECT to_char(returned_at, 'YYYY-MM') AS month, SUM(credit_amount) AS returns_total, SUM(cost_amount) AS returns_cost
      FROM sale_returns GROUP BY 1
), buy_m AS (
    SELECT to_char(received_date, 'YYYY-MM') AS month, SUM(quantity_received * buying_price) AS stock_bought
      FROM stock_batches GROUP BY 1
), exp_m AS (
    SELECT to_char(expense_date, 'YYYY-MM') AS month, SUM(amount) AS expenses_total
      FROM expenses GROUP BY 1
), paid_m AS (
    SELECT to_char(payment_date, 'YYYY-MM') AS month, SUM(amount) AS cash_collected
      FROM payments GROUP BY 1
), months AS (
    SELECT month FROM sales_m UNION SELECT month FROM cogs_m UNION SELECT month FROM ret_m
    UNION SELECT month FROM buy_m UNION SELECT month FROM exp_m UNION SELECT month FROM paid_m
)
SELECT m.month,
       COALESCE(s.sales_total, 0) - COALESCE(r.returns_total, 0) AS net_sales,
       COALESCE(c.cost_of_goods, 0) - COALESCE(r.returns_cost, 0) AS cost_of_goods,
       (COALESCE(s.sales_total, 0) - COALESCE(r.returns_total, 0))
         - (COALESCE(c.cost_of_goods, 0) - COALESCE(r.returns_cost, 0)) AS gross_profit,
       COALESCE(e.expenses_total, 0) AS expenses_total,
       (COALESCE(s.sales_total, 0) - COALESCE(r.returns_total, 0))
         - (COALESCE(c.cost_of_goods, 0) - COALESCE(r.returns_cost, 0))
         - COALESCE(e.expenses_total, 0) AS net_profit,
       COALESCE(b.stock_bought, 0) AS stock_purchased_value,
       COALESCE(p.cash_collected, 0) AS cash_collected
  FROM months m
  LEFT JOIN sales_m s ON s.month = m.month
  LEFT JOIN cogs_m c ON c.month = m.month
  LEFT JOIN ret_m r ON r.month = m.month
  LEFT JOIN buy_m b ON b.month = m.month
  LEFT JOIN exp_m e ON e.month = m.month
  LEFT JOIN paid_m p ON p.month = m.month
 ORDER BY m.month;

-- profit by item and by customer (after returns, before bill discounts)
CREATE VIEW v_profit_by_item AS
SELECT to_char(s.sale_date, 'YYYY-MM') AS month,
       p.product_name || ' - ' || t.type_name AS item,
       SUM(i.quantity - i.returned_quantity) AS qty_sold,
       SUM((i.quantity - i.returned_quantity) * i.unit_price) AS sales_value,
       SUM((i.quantity - i.returned_quantity) * i.buying_price) AS cost_value,
       SUM((i.quantity - i.returned_quantity) * (i.unit_price - i.buying_price)) AS profit
  FROM sale_items i
  JOIN sales s ON s.sale_id = i.sale_id AND s.status = 'completed'
  JOIN product_types t ON t.type_id = i.type_id
  JOIN products p ON p.product_id = t.product_id
 GROUP BY to_char(s.sale_date, 'YYYY-MM'), p.product_name, t.type_name;

CREATE VIEW v_profit_by_customer AS
SELECT to_char(s.sale_date, 'YYYY-MM') AS month, c.customer_name,
       SUM((i.quantity - i.returned_quantity) * i.unit_price) AS sales_value,
       SUM((i.quantity - i.returned_quantity) * i.buying_price) AS cost_value,
       SUM((i.quantity - i.returned_quantity) * (i.unit_price - i.buying_price)) AS profit
  FROM sale_items i
  JOIN sales s ON s.sale_id = i.sale_id AND s.status = 'completed'
  JOIN customers c ON c.customer_id = s.customer_id
 GROUP BY to_char(s.sale_date, 'YYYY-MM'), c.customer_name;

-- what each person did each day
CREATE VIEW v_daily_user_summary AS
WITH days AS (
    SELECT DISTINCT user_id, action_time::date AS day FROM activity_log
), bills AS (
    SELECT created_by AS user_id, created_at::date AS day,
           COUNT(*) FILTER (WHERE status = 'completed') AS bills_made,
           COALESCE(SUM(total) FILTER (WHERE status = 'completed'), 0) AS sales_total
      FROM sales GROUP BY 1, 2
), cash AS (
    SELECT received_by AS user_id, created_at::date AS day, SUM(amount) AS cash_received
      FROM payments GROUP BY 1, 2
), fixes AS (
    SELECT user_id, action_time::date AS day, COUNT(*) AS corrections
      FROM activity_log
     WHERE action_type IN ('stock_adjusted', 'sale_cancelled', 'sale_returned', 'price_changed')
     GROUP BY 1, 2
)
SELECT d.day, u.full_name AS person, u.user_role,
       COALESCE(b.bills_made, 0) AS bills_made,
       COALESCE(b.sales_total, 0) AS sales_total,
       COALESCE(ch.cash_received, 0) AS cash_received,
       COALESCE(f.corrections, 0) AS corrections
  FROM days d
  JOIN app_users u ON u.user_id = d.user_id
  LEFT JOIN bills b ON b.user_id = d.user_id AND b.day = d.day
  LEFT JOIN cash ch ON ch.user_id = d.user_id AND ch.day = d.day
  LEFT JOIN fixes f ON f.user_id = d.user_id AND f.day = d.day
 ORDER BY d.day DESC, u.full_name;

-- home screen numbers
CREATE VIEW v_today AS
SELECT
    (SELECT COALESCE(SUM(total), 0) FROM sales WHERE status = 'completed' AND sale_date = CURRENT_DATE) AS sales_today,
    (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date = CURRENT_DATE) AS cash_received_today,
    (SELECT COALESCE(SUM(balance), 0) FROM customers WHERE balance > 0) AS owed_to_you,
    (SELECT COUNT(*) FROM v_stock_by_type WHERE low_stock) AS low_stock_items;
