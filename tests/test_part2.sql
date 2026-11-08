-- TEST DATA + CHECKS for selling. Run AFTER test_part1.sql, on a test database only, and only ONCE.
SELECT sign_in('kumar', '3333');

SELECT create_customer((SELECT user_id FROM app_users WHERE username = 'meena'), 'Nimal Stores', '077-1111111', NULL, NULL, 50000,
                       (SELECT group_id FROM customer_groups WHERE group_name = 'Regular'));
SELECT create_customer((SELECT user_id FROM app_users WHERE username = 'meena'), 'Kamal Hotel', '071-2222222');

-- Kumar (employee) sells 40 cans to the REGULAR customer: oldest batch, 4,000 paid
SELECT create_sale(
    (SELECT user_id FROM app_users WHERE username = 'kumar'),
    (SELECT customer_id FROM customers WHERE customer_name = 'Nimal Stores'),
    jsonb_build_array(jsonb_build_object('type_id', (SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)'), 'quantity', 40)),
    0, 4000, (SELECT method_id FROM payment_methods WHERE method_name = 'Cash'));

-- Meena sells 30 cans to the NEW customer: newest batch, nothing paid
SELECT create_sale(
    (SELECT user_id FROM app_users WHERE username = 'meena'),
    (SELECT customer_id FROM customers WHERE customer_name = 'Kamal Hotel'),
    jsonb_build_array(jsonb_build_object('type_id', (SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)'), 'quantity', 30)));

-- Meena takes back 5 cans from Nimal's bill
SELECT return_sale_item(
    (SELECT user_id FROM app_users WHERE username = 'meena'),
    (SELECT i.sale_item_id FROM sale_items i JOIN sales s ON s.sale_id = i.sale_id
       WHERE s.customer_id = (SELECT customer_id FROM customers WHERE customer_name = 'Nimal Stores') LIMIT 1),
    5, 'Customer returned 5 damaged cans');

-- Kamal pays 3,000 on account
SELECT receive_payment((SELECT user_id FROM app_users WHERE username = 'meena'),
                       (SELECT customer_id FROM customers WHERE customer_name = 'Kamal Hotel'), 3000,
                       (SELECT method_id FROM payment_methods WHERE method_name = 'Cash'));

-- an empty bottle type that customers hold, and the movement for Nimal
INSERT INTO product_types (product_id, type_name, unit_id, is_returnable_container)
    SELECT p.product_id, '19 L Bottle (empty/new)', u.unit_id, true
      FROM products p, units u WHERE p.product_name = 'Drinking Water' AND u.unit_name = 'bottle';
SELECT record_container_movement((SELECT user_id FROM app_users WHERE username = 'kumar'),
       (SELECT customer_id FROM customers WHERE customer_name = 'Nimal Stores'),
       (SELECT type_id FROM product_types WHERE type_name = '19 L Bottle (empty/new)'), 40, 10);

-- a fuel expense, and a payment to the supplier
SELECT record_expense((SELECT user_id FROM app_users WHERE username = 'meena'),
       (SELECT expense_category_id FROM expense_categories WHERE expense_category_name = 'Fuel'), 1000);
SELECT pay_supplier((SELECT user_id FROM app_users WHERE username = 'owner'),
       (SELECT supplier_id FROM suppliers WHERE supplier_name = 'Main Factory'), 10000,
       (SELECT method_id FROM payment_methods WHERE method_name = 'Cash'));

-- CHECKS (run each one; expected results in the comments)
-- SELECT * FROM v_sale_item_details;   -- Nimal (Regular): 40 from B-000001 at 250;  Kamal (New): 30 from B-000002 at 260
-- SELECT customer_name, group_name, balance, balance_note FROM v_customer_balances;   -- Nimal 4750, Kamal 4800
-- SELECT * FROM v_batch_queue;         -- B-000001: 55 left;  B-000002: 70 left
-- SELECT * FROM v_monthly_summary;     -- net_sales 16550, cost_of_goods 10350, gross_profit 6200,
--                                      -- expenses_total 1000, net_profit 5200, stock_purchased_value 32000, cash_collected 7000
-- SELECT * FROM v_customer_containers; -- Nimal holds 30
-- SELECT * FROM v_supplier_balances;   -- Main Factory: you_owe 22000
-- SELECT * FROM v_today;               -- sales_today 17800, cash_received_today 7000, owed_to_you 9550, low_stock_items 0
