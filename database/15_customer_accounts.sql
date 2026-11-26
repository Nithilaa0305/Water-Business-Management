-- 15: customer account posting and payments

-- every change to what a customer owes goes through here
CREATE FUNCTION post_ledger(
    p_customer_id uuid, p_type text, p_ref_type text, p_ref_id uuid,
    p_debit numeric, p_credit numeric, p_note text, p_user_id uuid
) RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE
    v_balance numeric;
BEGIN
    UPDATE customers
       SET balance = balance + p_debit - p_credit, updated_at = CURRENT_TIMESTAMP
     WHERE customer_id = p_customer_id
    RETURNING balance INTO v_balance;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer not found';
    END IF;

    INSERT INTO customer_ledger (customer_id, entry_type, reference_type, reference_id,
                                 debit, credit, running_balance, note, created_by)
    VALUES (p_customer_id, p_type, p_ref_type, p_ref_id, p_debit, p_credit, v_balance, p_note, p_user_id);
    RETURN v_balance;
END;
$$;

CREATE FUNCTION receive_payment(
    p_user_id uuid, p_customer_id uuid, p_amount numeric, p_method_id uuid DEFAULT NULL,
    p_sale_id uuid DEFAULT NULL, p_notes text DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_payment_id uuid;
    v_name text;
    v_balance numeric;
    v_sale_customer uuid;
    v_sale_status text;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager', 'employee']);
    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Payment amount must be greater than zero';
    END IF;

    SELECT customer_name INTO v_name FROM customers WHERE customer_id = p_customer_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer not found';
    END IF;

    IF p_sale_id IS NOT NULL THEN
        SELECT customer_id, status INTO v_sale_customer, v_sale_status FROM sales WHERE sale_id = p_sale_id FOR UPDATE;
        IF NOT FOUND OR v_sale_customer <> p_customer_id OR v_sale_status <> 'completed' THEN
            RAISE EXCEPTION 'The bill must be a completed bill of the same customer';
        END IF;
        UPDATE sales SET amount_paid = amount_paid + p_amount WHERE sale_id = p_sale_id;
    END IF;

    INSERT INTO payments (customer_id, sale_id, amount, method_id, notes, received_by)
    VALUES (p_customer_id, p_sale_id, p_amount, p_method_id, p_notes, p_user_id)
    RETURNING payment_id INTO v_payment_id;

    v_balance := post_ledger(p_customer_id, 'payment', 'payment', v_payment_id, 0, p_amount, p_notes, p_user_id);

    PERFORM log_activity(p_user_id, 'payment_received',
        'Received ' || p_amount || ' from ' || v_name || '. Balance now ' || v_balance, 'payment', v_payment_id);
    RETURN v_payment_id;
END;
$$;
