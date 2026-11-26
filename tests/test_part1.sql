-- TEST DATA + CHECKS for the stock side. Use ONLY on a test database, never on the real one.
-- Safe to run again: it skips anything that already exists.
SELECT create_user('Owner', 'owner', '1234', 'owner')
 WHERE NOT EXISTS (SELECT 1 FROM app_users WHERE username = 'owner');
SELECT create_user('Meena', 'meena', '2222', 'manager', (SELECT user_id FROM app_users WHERE username = 'owner'))
 WHERE NOT EXISTS (SELECT 1 FROM app_users WHERE username = 'meena');
SELECT create_user('Kumar', 'kumar', '3333', 'employee', (SELECT user_id FROM app_users WHERE username = 'owner'))
 WHERE NOT EXISTS (SELECT 1 FROM app_users WHERE username = 'kumar');
SELECT sign_in('meena', '2222');

INSERT INTO categories (category_name) VALUES ('Water') ON CONFLICT DO NOTHING;
INSERT INTO products (category_id, product_name)
    SELECT category_id, 'Drinking Water' FROM categories WHERE category_name = 'Water'
    ON CONFLICT DO NOTHING;
INSERT INTO product_types (product_id, type_name, unit_id, low_stock_limit)
    SELECT p.product_id, '19 L Water (filled)', u.unit_id, 20
      FROM products p, units u WHERE p.product_name = 'Drinking Water' AND u.unit_name = 'can'
    ON CONFLICT DO NOTHING;
INSERT INTO suppliers (supplier_name)
    SELECT 'Main Factory' WHERE NOT EXISTS (SELECT 1 FROM suppliers WHERE supplier_name = 'Main Factory');

DO $$
DECLARE
    v_meena uuid := (SELECT user_id FROM app_users WHERE username = 'meena');
    v_type uuid := (SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)');
    v_supplier uuid := (SELECT supplier_id FROM suppliers WHERE supplier_name = 'Main Factory' LIMIT 1);
BEGIN
    IF EXISTS (SELECT 1 FROM stock_batches) THEN
        RAISE NOTICE 'Stock already added - skipped';
        RETURN;
    END IF;
    PERFORM receive_stock(v_meena, v_type, 100, 150, 250, v_supplier);
    PERFORM receive_stock(v_meena, v_type, 100, 170, 260, v_supplier);
    PERFORM adjust_stock(v_meena, (SELECT batch_id FROM stock_batches WHERE buying_price = 150),
                         90, 'Damaged in handling', 'damaged');
END;
$$;

-- CHECKS (run each one; expected results in the comments)
-- SELECT * FROM v_batch_queue;      -- B-000001 Current, 90 left (150 / 250);  B-000002 Next, 100 left (170 / 260)
-- SELECT * FROM v_stock_by_type;    -- total 190 in 2 batches, low_stock false
-- SELECT * FROM v_price_history;    -- 4 rows: buying 150, selling 250, buying 170 (old 150), selling 260 (old 250)
-- SELECT action_time, person, action_type, description FROM v_activity_timeline;   -- at least 6 lines
-- SELECT * FROM pick_batches((SELECT type_id FROM product_types WHERE type_name = '19 L Water (filled)'), 120);
--        -- 90 from B-000001 and 30 from B-000002
