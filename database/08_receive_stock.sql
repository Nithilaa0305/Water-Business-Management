-- 08: receive stock (creates a batch)
CREATE FUNCTION receive_stock(
    p_user_id uuid, p_type_id uuid, p_quantity integer, p_buying_price numeric,
    p_selling_price numeric DEFAULT NULL, p_supplier_id uuid DEFAULT NULL,
    p_supplier_invoice_no text DEFAULT NULL, p_expiry_date date DEFAULT NULL,
    p_received_date date DEFAULT CURRENT_DATE, p_notes text DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_batch_id uuid;
    v_batch_number text;
    v_item text;
    v_last_buying numeric;
    v_last_selling numeric;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);

    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Quantity must be greater than zero';
    END IF;
    IF p_buying_price < 0 THEN
        RAISE EXCEPTION 'Buying price cannot be negative';
    END IF;
    IF p_selling_price IS NOT NULL AND p_selling_price < 0 THEN
        RAISE EXCEPTION 'Selling price cannot be negative';
    END IF;

    SELECT p.product_name || ' - ' || t.type_name INTO v_item
      FROM product_types t JOIN products p ON p.product_id = t.product_id
     WHERE t.type_id = p_type_id AND t.is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product type not found or not active';
    END IF;

    -- previous prices, so the history shows old -> new
    SELECT buying_price INTO v_last_buying FROM stock_batches
     WHERE type_id = p_type_id ORDER BY received_date DESC, created_at DESC, batch_number DESC LIMIT 1;
    SELECT new_price INTO v_last_selling FROM price_history
     WHERE type_id = p_type_id AND price_kind = 'selling' ORDER BY changed_at DESC LIMIT 1;

    INSERT INTO stock_batches (type_id, supplier_id, supplier_invoice_no, quantity_received, current_quantity,
                               buying_price, selling_price, expiry_date, received_date, created_by)
    VALUES (p_type_id, p_supplier_id, p_supplier_invoice_no, p_quantity, p_quantity,
            p_buying_price, p_selling_price, p_expiry_date, p_received_date, p_user_id)
    RETURNING batch_id, batch_number INTO v_batch_id, v_batch_number;

    INSERT INTO inventory_transactions (batch_id, transaction_type, quantity, quantity_change,
                                        reference_type, reference_id, reference_note, created_by)
    VALUES (v_batch_id, 'stock_received', p_quantity, p_quantity,
            'stock_batch', v_batch_id, COALESCE(p_notes, 'Stock received'), p_user_id);

    INSERT INTO price_history (type_id, batch_id, price_kind, old_price, new_price, changed_by, note)
    VALUES (p_type_id, v_batch_id, 'buying', v_last_buying, p_buying_price, p_user_id, 'Batch ' || v_batch_number);

    IF p_selling_price IS NOT NULL AND p_selling_price IS DISTINCT FROM v_last_selling THEN
        INSERT INTO price_history (type_id, batch_id, price_kind, old_price, new_price, changed_by, note)
        VALUES (p_type_id, v_batch_id, 'selling', v_last_selling, p_selling_price, p_user_id, 'Batch ' || v_batch_number);
    END IF;

    PERFORM log_activity(p_user_id, 'stock_received',
        'Received ' || p_quantity || ' x ' || v_item || ' as batch ' || v_batch_number
        || ' at buying price ' || p_buying_price, 'stock_batch', v_batch_id);

    RETURN v_batch_id;
END;
$$;
