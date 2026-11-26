-- 09: correct stock and change a selling price
CREATE FUNCTION adjust_stock(
    p_user_id uuid, p_batch_id uuid, p_new_quantity integer, p_reason text,
    p_reason_type text DEFAULT 'adjustment'
) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    v_old integer;
    v_diff integer;
    v_number text;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);

    IF p_new_quantity < 0 THEN
        RAISE EXCEPTION 'Stock quantity cannot be negative';
    END IF;
    IF p_reason IS NULL OR trim(p_reason) = '' THEN
        RAISE EXCEPTION 'A reason is required for a stock correction';
    END IF;
    IF p_reason_type NOT IN ('adjustment', 'damaged', 'expired') THEN
        RAISE EXCEPTION 'Reason type must be adjustment, damaged or expired';
    END IF;

    SELECT current_quantity, batch_number INTO v_old, v_number
      FROM stock_batches WHERE batch_id = p_batch_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Stock batch not found';
    END IF;

    v_diff := p_new_quantity - v_old;
    IF v_diff = 0 THEN
        RAISE EXCEPTION 'New quantity is the same as the current quantity';
    END IF;

    UPDATE stock_batches
       SET current_quantity = p_new_quantity, updated_at = CURRENT_TIMESTAMP
     WHERE batch_id = p_batch_id;

    INSERT INTO inventory_transactions (batch_id, transaction_type, quantity, quantity_change,
                                        reference_type, reference_id, reference_note, created_by)
    VALUES (p_batch_id, p_reason_type, abs(v_diff), v_diff, 'stock_batch', p_batch_id, p_reason, p_user_id);

    PERFORM log_activity(p_user_id, 'stock_adjusted',
        'Changed batch ' || v_number || ' from ' || v_old || ' to ' || p_new_quantity || '. Reason: ' || p_reason,
        'stock_batch', p_batch_id);

    RETURN p_new_quantity;
END;
$$;

CREATE FUNCTION set_batch_selling_price(
    p_user_id uuid, p_batch_id uuid, p_new_price numeric, p_note text DEFAULT NULL
) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_type uuid;
    v_old numeric;
    v_number text;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);

    IF p_new_price < 0 THEN
        RAISE EXCEPTION 'Selling price cannot be negative';
    END IF;

    SELECT type_id, selling_price, batch_number INTO v_type, v_old, v_number
      FROM stock_batches WHERE batch_id = p_batch_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Stock batch not found';
    END IF;
    IF v_old IS NOT DISTINCT FROM p_new_price THEN
        RAISE EXCEPTION 'The selling price is already %', p_new_price;
    END IF;

    UPDATE stock_batches
       SET selling_price = p_new_price, updated_at = CURRENT_TIMESTAMP
     WHERE batch_id = p_batch_id;

    INSERT INTO price_history (type_id, batch_id, price_kind, old_price, new_price, changed_by, note)
    VALUES (v_type, p_batch_id, 'selling', v_old, p_new_price, p_user_id, p_note);

    PERFORM log_activity(p_user_id, 'price_changed',
        'Changed selling price of batch ' || v_number || ' from ' || COALESCE(v_old::text, 'not set')
        || ' to ' || p_new_price, 'stock_batch', p_batch_id);
END;
$$;
