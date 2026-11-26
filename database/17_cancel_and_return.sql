-- 17: cancel a bill and return items
CREATE FUNCTION cancel_sale(p_user_id uuid, p_sale_id uuid, p_reason text) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_sale sales%ROWTYPE;
    v_name text;
    r record;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);
    IF p_reason IS NULL OR trim(p_reason) = '' THEN
        RAISE EXCEPTION 'A reason is required to cancel a bill';
    END IF;

    SELECT * INTO v_sale FROM sales WHERE sale_id = p_sale_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Bill not found';
    END IF;
    IF v_sale.status <> 'completed' THEN
        RAISE EXCEPTION 'This bill is already cancelled';
    END IF;
    IF EXISTS (SELECT 1 FROM sale_returns WHERE sale_id = p_sale_id) THEN
        RAISE EXCEPTION 'This bill already has returns, so it cannot be cancelled';
    END IF;

    SELECT customer_name INTO v_name FROM customers WHERE customer_id = v_sale.customer_id FOR UPDATE;

    FOR r IN SELECT batch_id, quantity FROM sale_items WHERE sale_id = p_sale_id LOOP
        UPDATE stock_batches SET current_quantity = current_quantity + r.quantity, updated_at = CURRENT_TIMESTAMP
         WHERE batch_id = r.batch_id;
        INSERT INTO inventory_transactions (batch_id, transaction_type, quantity, quantity_change,
                                            reference_type, reference_id, reference_note, created_by)
        VALUES (r.batch_id, 'sale_cancelled', r.quantity, r.quantity, 'sale', p_sale_id,
                'Cancelled bill ' || v_sale.sale_number || ': ' || p_reason, p_user_id);
    END LOOP;

    UPDATE sales
       SET status = 'cancelled', cancelled_by = p_user_id, cancelled_at = clock_timestamp(), cancel_reason = p_reason
     WHERE sale_id = p_sale_id;

    PERFORM post_ledger(v_sale.customer_id, 'sale_cancelled', 'sale', p_sale_id, 0, v_sale.total,
                        'Cancelled bill ' || v_sale.sale_number, p_user_id);

    PERFORM log_activity(p_user_id, 'sale_cancelled',
        'Cancelled bill ' || v_sale.sale_number || ' of ' || v_name || ' (' || v_sale.total || '). Reason: ' || p_reason,
        'sale', p_sale_id);
END;
$$;

CREATE FUNCTION return_sale_item(p_user_id uuid, p_sale_item_id uuid, p_quantity integer, p_reason text)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_item sale_items%ROWTYPE;
    v_sale sales%ROWTYPE;
    v_credit numeric;
    v_cost numeric;
    v_return_id uuid;
    v_name text;
    v_balance numeric;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);
    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Return quantity must be greater than zero';
    END IF;
    IF p_reason IS NULL OR trim(p_reason) = '' THEN
        RAISE EXCEPTION 'A reason is required for a return';
    END IF;

    SELECT * INTO v_item FROM sale_items WHERE sale_item_id = p_sale_item_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Bill item not found';
    END IF;
    SELECT * INTO v_sale FROM sales WHERE sale_id = v_item.sale_id FOR UPDATE;
    IF v_sale.status <> 'completed' THEN
        RAISE EXCEPTION 'Only completed bills can have returns';
    END IF;
    IF v_item.returned_quantity + p_quantity > v_item.quantity THEN
        RAISE EXCEPTION 'Only % of this item can still be returned', v_item.quantity - v_item.returned_quantity;
    END IF;

    v_credit := p_quantity * v_item.unit_price;
    v_cost := p_quantity * v_item.buying_price;
    SELECT customer_name INTO v_name FROM customers WHERE customer_id = v_sale.customer_id FOR UPDATE;

    UPDATE sale_items SET returned_quantity = returned_quantity + p_quantity WHERE sale_item_id = p_sale_item_id;
    UPDATE stock_batches SET current_quantity = current_quantity + p_quantity, updated_at = CURRENT_TIMESTAMP
     WHERE batch_id = v_item.batch_id;
    INSERT INTO inventory_transactions (batch_id, transaction_type, quantity, quantity_change,
                                        reference_type, reference_id, reference_note, created_by)
    VALUES (v_item.batch_id, 'sale_return', p_quantity, p_quantity, 'sale', v_sale.sale_id,
            'Return on bill ' || v_sale.sale_number || ': ' || p_reason, p_user_id);

    INSERT INTO sale_returns (sale_id, sale_item_id, customer_id, quantity, credit_amount, cost_amount, reason, returned_by)
    VALUES (v_sale.sale_id, p_sale_item_id, v_sale.customer_id, p_quantity, v_credit, v_cost, p_reason, p_user_id)
    RETURNING return_id INTO v_return_id;

    v_balance := post_ledger(v_sale.customer_id, 'sale_return', 'sale_return', v_return_id, 0, v_credit,
                             'Return on bill ' || v_sale.sale_number, p_user_id);

    PERFORM log_activity(p_user_id, 'sale_returned',
        'Took back ' || p_quantity || ' on bill ' || v_sale.sale_number || ' from ' || v_name
        || ', credit ' || v_credit || '. Reason: ' || p_reason, 'sale_return', v_return_id);
    RETURN v_return_id;
END;
$$;
