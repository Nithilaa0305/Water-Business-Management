-- 10: pick batches oldest-first (the simple rule; sales use pick_batches_by_rule in file 12)
CREATE FUNCTION pick_batches(p_type_id uuid, p_quantity integer)
RETURNS TABLE (out_batch_id uuid, out_batch_number varchar, out_quantity integer,
               out_buying_price numeric, out_selling_price numeric)
LANGUAGE plpgsql AS $$
DECLARE
    v_remaining integer := p_quantity;
    v_take integer;
    v_available integer;
    r record;
BEGIN
    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Quantity must be greater than zero';
    END IF;

    FOR r IN
        SELECT b.batch_id AS bid, b.batch_number AS bno, b.current_quantity AS qty,
               b.buying_price AS bp, b.selling_price AS sp
          FROM stock_batches b
         WHERE b.type_id = p_type_id AND b.current_quantity > 0
         ORDER BY b.received_date, b.created_at, b.batch_number
           FOR UPDATE
    LOOP
        EXIT WHEN v_remaining = 0;
        v_take := LEAST(r.qty, v_remaining);
        out_batch_id := r.bid;
        out_batch_number := r.bno;
        out_quantity := v_take;
        out_buying_price := r.bp;
        out_selling_price := r.sp;
        RETURN NEXT;
        v_remaining := v_remaining - v_take;
    END LOOP;

    IF v_remaining > 0 THEN
        SELECT COALESCE(SUM(sb.current_quantity), 0) INTO v_available
          FROM stock_batches sb WHERE sb.type_id = p_type_id;
        RAISE EXCEPTION 'Not enough stock: need %, have %', p_quantity, v_available;
    END IF;
END;
$$;
