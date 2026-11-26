-- 12: customer groups, the batch rule, customer functions
CREATE TABLE customer_groups (
    group_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    group_name varchar(100) NOT NULL UNIQUE,
    batch_rule varchar(10) NOT NULL DEFAULT 'oldest',
    is_active boolean NOT NULL DEFAULT true,
    CONSTRAINT chk_group_batch_rule CHECK (batch_rule IN ('oldest', 'newest'))
);

INSERT INTO customer_groups (group_name, batch_rule) VALUES ('Regular', 'oldest'), ('New', 'newest');

ALTER TABLE customers ADD COLUMN group_id uuid REFERENCES customer_groups(group_id);
UPDATE customers SET group_id = (SELECT group_id FROM customer_groups WHERE group_name = 'New') WHERE group_id IS NULL;

CREATE FUNCTION create_customer(
    p_user_id uuid, p_name text, p_phone text DEFAULT NULL, p_address text DEFAULT NULL,
    p_area_id uuid DEFAULT NULL, p_credit_limit numeric DEFAULT 0,
    p_group_id uuid DEFAULT NULL, p_notes text DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_role text;
    v_id uuid;
    v_group uuid;
BEGIN
    v_role := check_role(p_user_id, ARRAY['owner', 'manager', 'employee']);
    IF p_name IS NULL OR trim(p_name) = '' THEN
        RAISE EXCEPTION 'Customer name is required';
    END IF;
    IF p_credit_limit < 0 THEN
        RAISE EXCEPTION 'Credit limit cannot be negative';
    END IF;
    IF v_role = 'employee' AND (p_credit_limit <> 0 OR p_group_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Only a manager or the owner can set the credit limit or group';
    END IF;

    v_group := COALESCE(p_group_id, (SELECT group_id FROM customer_groups WHERE group_name = 'New'));

    INSERT INTO customers (customer_name, phone, address, area_id, credit_limit, group_id, notes)
    VALUES (trim(p_name), p_phone, p_address, p_area_id, p_credit_limit, v_group, p_notes)
    RETURNING customer_id INTO v_id;

    PERFORM log_activity(p_user_id, 'customer_created', 'Added customer ' || trim(p_name), 'customer', v_id);
    RETURN v_id;
END;
$$;

CREATE FUNCTION set_customer_group(p_user_id uuid, p_customer_id uuid, p_group_id uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_name text;
    v_old text;
    v_new text;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);
    SELECT c.customer_name, g.group_name INTO v_name, v_old
      FROM customers c LEFT JOIN customer_groups g ON g.group_id = c.group_id
     WHERE c.customer_id = p_customer_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer not found';
    END IF;
    SELECT group_name INTO v_new FROM customer_groups WHERE group_id = p_group_id AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer group not found';
    END IF;

    UPDATE customers SET group_id = p_group_id, updated_at = CURRENT_TIMESTAMP WHERE customer_id = p_customer_id;
    PERFORM log_activity(p_user_id, 'customer_group_changed',
        'Moved ' || v_name || ' from ' || COALESCE(v_old, 'no group') || ' to ' || v_new, 'customer', p_customer_id);
END;
$$;

CREATE FUNCTION set_credit_limit(p_user_id uuid, p_customer_id uuid, p_new_limit numeric) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_name text;
    v_old numeric;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);
    IF p_new_limit < 0 THEN
        RAISE EXCEPTION 'Credit limit cannot be negative';
    END IF;
    SELECT customer_name, credit_limit INTO v_name, v_old FROM customers WHERE customer_id = p_customer_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer not found';
    END IF;

    UPDATE customers SET credit_limit = p_new_limit, updated_at = CURRENT_TIMESTAMP WHERE customer_id = p_customer_id;
    PERFORM log_activity(p_user_id, 'credit_limit_changed',
        'Changed credit limit of ' || v_name || ' from ' || v_old || ' to ' || p_new_limit, 'customer', p_customer_id);
END;
$$;

-- picks batches by the customer's rule: 'oldest' or 'newest'
CREATE FUNCTION pick_batches_by_rule(p_type_id uuid, p_quantity integer, p_rule text DEFAULT 'oldest')
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
    IF p_rule NOT IN ('oldest', 'newest') THEN
        RAISE EXCEPTION 'Batch rule must be oldest or newest';
    END IF;

    FOR r IN
        SELECT b.batch_id AS bid, b.batch_number AS bno, b.current_quantity AS qty,
               b.buying_price AS bp, b.selling_price AS sp
          FROM stock_batches b
         WHERE b.type_id = p_type_id AND b.current_quantity > 0
         ORDER BY CASE WHEN p_rule = 'newest' THEN -(b.received_date - DATE '2000-01-01')
                       ELSE (b.received_date - DATE '2000-01-01') END,
                  CASE WHEN p_rule = 'newest' THEN -EXTRACT(EPOCH FROM b.created_at)
                       ELSE EXTRACT(EPOCH FROM b.created_at) END
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
