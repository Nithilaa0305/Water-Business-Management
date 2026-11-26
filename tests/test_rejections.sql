-- THESE MUST ALL FAIL. Run each statement ON ITS OWN (in pgAdmin, one at a time),
-- after test_part1.sql and test_part2.sql. The expected message is in the comment.

-- 0) set up first (this one succeeds):
-- SELECT set_credit_limit((SELECT user_id FROM app_users WHERE username = 'meena'),
--        (SELECT customer_id FROM customers WHERE customer_name = 'Kamal Hotel'), 5000);

-- 1) sale that would pass the credit limit   -> "Credit limit exceeded: balance would be 5060.00 and the limit is 5000.00"
-- SELECT create_sale((SELECT user_id FROM app_users WHERE username = 'kumar'),
--        (SELECT customer_id FROM customers WHERE customer_name = 'Kamal Hotel'),
--        jsonb_build_array(jsonb_build_object('type_id', (SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)'), 'quantity', 1)));

-- 2) employee goes over the limit by override -> "Only a manager or the owner can go over the credit limit"
-- SELECT create_sale((SELECT user_id FROM app_users WHERE username = 'kumar'),
--        (SELECT customer_id FROM customers WHERE customer_name = 'Kamal Hotel'),
--        jsonb_build_array(jsonb_build_object('type_id', (SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)'), 'quantity', 1)),
--        0, 0, NULL, NULL, true);

-- 3) employee chooses a batch by hand         -> "Only a manager or the owner can choose the batch by hand"
-- SELECT create_sale((SELECT user_id FROM app_users WHERE username = 'kumar'),
--        (SELECT customer_id FROM customers WHERE customer_name = 'Nimal Stores'),
--        jsonb_build_array(jsonb_build_object('type_id', (SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)'),
--                                             'quantity', 1, 'batch_id', (SELECT batch_id FROM stock_batches WHERE batch_number = 'B-000002'))));

-- 4) selling more than the stock              -> "Not enough stock: need 500, have 125"
-- SELECT create_sale((SELECT user_id FROM app_users WHERE username = 'meena'),
--        (SELECT customer_id FROM customers WHERE customer_name = 'Nimal Stores'),
--        jsonb_build_array(jsonb_build_object('type_id', (SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)'), 'quantity', 500)));

-- 5) employee cancels a bill                  -> "Your role (employee) is not allowed to do this"
-- SELECT cancel_sale((SELECT user_id FROM app_users WHERE username = 'kumar'),
--        (SELECT sale_id FROM sales ORDER BY created_at LIMIT 1), 'test');

-- 6) returning more than was sold             -> "Only 35 of this item can still be returned"
-- SELECT return_sale_item((SELECT user_id FROM app_users WHERE username = 'meena'),
--        (SELECT i.sale_item_id FROM sale_items i JOIN sales s ON s.sale_id = i.sale_id
--           WHERE s.customer_id = (SELECT customer_id FROM customers WHERE customer_name = 'Nimal Stores') LIMIT 1),
--        100, 'test');

-- 7) employee receives stock                  -> "Your role (employee) is not allowed to do this"
-- SELECT receive_stock((SELECT user_id FROM app_users WHERE username = 'kumar'),
--        (SELECT type_id FROM product_types LIMIT 1), 10, 150);

-- 8) stock correction without a reason        -> "A reason is required for a stock correction"
-- SELECT adjust_stock((SELECT user_id FROM app_users WHERE username = 'meena'),
--        (SELECT batch_id FROM stock_batches LIMIT 1), 50, '');

-- 9) deleting the activity record             -> "The activity record cannot be changed or deleted"
-- DELETE FROM activity_log;

-- AFTER the tests, nothing should have changed:
-- SELECT (SELECT COUNT(*) FROM sales) AS bills,
--        (SELECT balance FROM customers WHERE customer_name = 'Kamal Hotel') AS kamal_balance,
--        (SELECT current_quantity FROM stock_batches WHERE batch_number = 'B-000002') AS b2_stock;
--        -- expect: 2, 4800.00, 70
