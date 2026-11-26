-- 16: make a bill
-- p_items is a JSON array, for example:
--   [{"type_id": "<uuid>", "quantity": 10, "price": 250, "batch_id": null}]
-- "price" and "batch_id" are optional. Without a batch_id the customer's group rule picks the batch.
CREATE FUNCTION create_sale(
    p_user_id uuid, p_customer_id uuid, p_items jsonb,
    p_discount numeric DEFAULT 0, p_amount_paid numeric DEFAULT 0,
    p_method_id uuid DEFAULT NULL, p_notes text DEFAULT NULL,
    p_allow_over_limit boolean DEFAULT false
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_role text;
    v_cust customers%ROWTYPE;
    v_rule text;
    v_sale_id uuid;
    v_sale_number text;
    v_item jsonb;
    v_type_id uuid;
    v_qty integer;
    v_price numeric;
    v_batch uuid;
    v_item_name text;
    v_default_price numeric;
    v_unit_price numeric;
    v_batch_type uuid;
    v_batch_qty integer;
    v_batch_price numeric;
    v_batch_buying numeric;
    v_batch_number text;
    r record;
    v_subtotal numeric := 0;
    v_total numeric;
    v_balance numeric;
BEGIN
    v_role := check_role(p_user_id, ARRAY['owner', 'manager', 'employee']);

    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'The bill has no items';
    END IF;
    IF p_discount < 0 OR p_amount_paid < 0 THEN
        RAISE EXCEPTION 'Discount and amount paid cannot be negative';
    END IF;

    SELECT * INTO v_cust FROM customers WHERE customer_id = p_customer_id AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer not found or not active';
    END IF;

    SELECT COALESCE(g.batch_rule, 'oldest') INTO v_rule
      FROM customers c LEFT JOIN customer_groups g ON g.group_id = c.group_id
     WHERE c.customer_id = p_customer_id;

    INSERT INTO sales (customer_id, created_by, discount, notes)
    VALUES (p_customer_id, p_user_id, p_discount, p_notes)
    RETURNING sale_id, sale_number INTO v_sale_id, v_sale_number;

    FOR v_item IN SELECT value FROM jsonb_array_elements(p_items) LOOP
        v_type_id := (v_item ->> 'type_id')::uuid;
        v_qty := (v_item ->> 'quantity')::integer;
        v_price := NULLIF(v_item ->> 'price', '')::numeric;
        v_batch := NULLIF(v_item ->> 'batch_id', '')::uuid;

        IF v_qty IS NULL OR v_qty <= 0 THEN
            RAISE EXCEPTION 'Each item needs a quantity above zero';
        END IF;

        SELECT p.product_name || ' - ' || t.type_name, NULLIF(t.default_selling_price, 0)
          INTO v_item_name, v_default_price
          FROM product_types t JOIN products p ON p.product_id = t.product_id
         WHERE t.type_id = v_type_id AND t.is_active;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Product type not found or not active';
        END IF;

        IF v_batch IS NOT NULL THEN
            -- batch chosen by hand
            IF v_role = 'employee' THEN
                RAISE EXCEPTION 'Only a manager or the owner can choose the batch by hand';
            END IF;
            SELECT type_id, current_quantity, selling_price, buying_price, batch_number
              INTO v_batch_type, v_batch_qty, v_batch_price, v_batch_buying, v_batch_number
              FROM stock_batches WHERE batch_id = v_batch FOR UPDATE;
            IF NOT FOUND OR v_batch_type <> v_type_id THEN
                RAISE EXCEPTION 'The chosen batch does not belong to %', v_item_name;
            END IF;
            IF v_batch_qty < v_qty THEN
                RAISE EXCEPTION 'Batch % has only % left of %', v_batch_number, v_batch_qty, v_item_name;
            END IF;

            v_unit_price := COALESCE(v_price, v_batch_price, v_default_price);
            IF v_unit_price IS NULL THEN
                RAISE EXCEPTION 'No price for %: please type a price', v_item_name;
            END IF;

            INSERT INTO sale_items (sale_id, type_id, batch_id, quantity, unit_price, buying_price)
            VALUES (v_sale_id, v_type_id, v_batch, v_qty, v_unit_price, v_batch_buying);
            UPDATE stock_batches SET current_quantity = current_quantity - v_qty, updated_at = CURRENT_TIMESTAMP
             WHERE batch_id = v_batch;
            INSERT INTO inventory_transactions (batch_id, transaction_type, quantity, quantity_change,
                                                reference_type, reference_id, reference_note, created_by)
            VALUES (v_batch, 'sold', v_qty, -v_qty, 'sale', v_sale_id, 'Bill ' || v_sale_number, p_user_id);
            v_subtotal := v_subtotal + v_qty * v_unit_price;
        ELSE
            -- batch chosen by the customer's group rule
            FOR r IN SELECT * FROM pick_batches_by_rule(v_type_id, v_qty, v_rule) LOOP
                v_unit_price := COALESCE(v_price, r.out_selling_price, v_default_price);
                IF v_unit_price IS NULL THEN
                    RAISE EXCEPTION 'No price for %: please type a price', v_item_name;
                END IF;

                INSERT INTO sale_items (sale_id, type_id, batch_id, quantity, unit_price, buying_price)
                VALUES (v_sale_id, v_type_id, r.out_batch_id, r.out_quantity, v_unit_price, r.out_buying_price);
                UPDATE stock_batches SET current_quantity = current_quantity - r.out_quantity, updated_at = CURRENT_TIMESTAMP
                 WHERE batch_id = r.out_batch_id;
                INSERT INTO inventory_transactions (batch_id, transaction_type, quantity, quantity_change,
                                                    reference_type, reference_id, reference_note, created_by)
                VALUES (r.out_batch_id, 'sold', r.out_quantity, -r.out_quantity, 'sale', v_sale_id,
                        'Bill ' || v_sale_number, p_user_id);
                v_subtotal := v_subtotal + r.out_quantity * v_unit_price;
            END LOOP;
        END IF;
    END LOOP;

    IF p_discount > v_subtotal THEN
        RAISE EXCEPTION 'Discount (%) is bigger than the bill amount (%)', p_discount, v_subtotal;
    END IF;
    v_total := v_subtotal - p_discount;
    IF p_amount_paid > v_total THEN
        RAISE EXCEPTION 'Amount paid is more than the bill total; record the extra as a separate payment';
    END IF;

    IF v_cust.credit_limit > 0 AND (v_cust.balance + v_total - p_amount_paid) > v_cust.credit_limit THEN
        IF NOT p_allow_over_limit THEN
            RAISE EXCEPTION 'Credit limit exceeded: balance would be % and the limit is %',
                            v_cust.balance + v_total - p_amount_paid, v_cust.credit_limit;
        ELSIF v_role = 'employee' THEN
            RAISE EXCEPTION 'Only a manager or the owner can go over the credit limit';
        END IF;
    END IF;

    UPDATE sales SET subtotal = v_subtotal, total = v_total WHERE sale_id = v_sale_id;

    PERFORM post_ledger(p_customer_id, 'sale', 'sale', v_sale_id, v_total, 0, 'Bill ' || v_sale_number, p_user_id);

    IF p_amount_paid > 0 THEN
        PERFORM receive_payment(p_user_id, p_customer_id, p_amount_paid, p_method_id, v_sale_id, 'Paid at billing');
    END IF;

    SELECT balance INTO v_balance FROM customers WHERE customer_id = p_customer_id;
    PERFORM log_activity(p_user_id, 'sale_created',
        'Made bill ' || v_sale_number || ' for ' || v_cust.customer_name || ', total ' || v_total
        || ', paid ' || p_amount_paid || '. Customer balance now ' || v_balance, 'sale', v_sale_id);

    RETURN v_sale_id;
END;
$$;
