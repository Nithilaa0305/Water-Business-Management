-- 18: returnable containers, expenses, supplier payments
CREATE FUNCTION record_container_movement(
    p_user_id uuid, p_customer_id uuid, p_type_id uuid, p_given integer, p_returned integer,
    p_sale_id uuid DEFAULT NULL, p_notes text DEFAULT NULL
) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    v_item text;
    v_name text;
    v_held integer;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager', 'employee']);
    IF p_given < 0 OR p_returned < 0 OR p_given + p_returned = 0 THEN
        RAISE EXCEPTION 'Enter how many were given or returned';
    END IF;

    SELECT p.product_name || ' - ' || t.type_name INTO v_item
      FROM product_types t JOIN products p ON p.product_id = t.product_id
     WHERE t.type_id = p_type_id AND t.is_returnable_container;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'This item is not set up as a returnable container';
    END IF;

    SELECT customer_name INTO v_name FROM customers WHERE customer_id = p_customer_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer not found';
    END IF;

    INSERT INTO customer_containers (customer_id, type_id, held) VALUES (p_customer_id, p_type_id, 0)
    ON CONFLICT (customer_id, type_id) DO NOTHING;

    SELECT held INTO v_held FROM customer_containers
     WHERE customer_id = p_customer_id AND type_id = p_type_id FOR UPDATE;
    IF v_held + p_given - p_returned < 0 THEN
        RAISE EXCEPTION '% holds only % of these', v_name, v_held;
    END IF;

    UPDATE customer_containers SET held = v_held + p_given - p_returned
     WHERE customer_id = p_customer_id AND type_id = p_type_id;

    INSERT INTO container_movements (customer_id, type_id, sale_id, given_qty, returned_qty, notes, created_by)
    VALUES (p_customer_id, p_type_id, p_sale_id, p_given, p_returned, p_notes, p_user_id);

    PERFORM log_activity(p_user_id, 'container_movement',
        v_name || ': ' || p_given || ' given, ' || p_returned || ' returned (' || v_item || '). Now holds '
        || (v_held + p_given - p_returned), 'customer', p_customer_id);
    RETURN v_held + p_given - p_returned;
END;
$$;

CREATE FUNCTION record_expense(
    p_user_id uuid, p_category_id uuid, p_amount numeric,
    p_date date DEFAULT CURRENT_DATE, p_notes text DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_id uuid;
    v_cat text;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);
    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Expense amount must be greater than zero';
    END IF;
    SELECT expense_category_name INTO v_cat FROM expense_categories WHERE expense_category_id = p_category_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Expense category not found';
    END IF;

    INSERT INTO expenses (expense_date, expense_category_id, amount, notes, created_by)
    VALUES (p_date, p_category_id, p_amount, p_notes, p_user_id)
    RETURNING expense_id INTO v_id;

    PERFORM log_activity(p_user_id, 'expense_recorded', 'Recorded expense ' || v_cat || ': ' || p_amount, 'expense', v_id);
    RETURN v_id;
END;
$$;

CREATE FUNCTION pay_supplier(
    p_user_id uuid, p_supplier_id uuid, p_amount numeric, p_method_id uuid DEFAULT NULL,
    p_date date DEFAULT CURRENT_DATE, p_notes text DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_id uuid;
    v_name text;
BEGIN
    PERFORM check_role(p_user_id, ARRAY['owner', 'manager']);
    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Payment amount must be greater than zero';
    END IF;
    SELECT supplier_name INTO v_name FROM suppliers WHERE supplier_id = p_supplier_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Supplier not found';
    END IF;

    INSERT INTO supplier_payments (supplier_id, payment_date, amount, method_id, notes, created_by)
    VALUES (p_supplier_id, p_date, p_amount, p_method_id, p_notes, p_user_id)
    RETURNING supplier_payment_id INTO v_id;

    PERFORM log_activity(p_user_id, 'supplier_paid', 'Paid supplier ' || v_name || ': ' || p_amount, 'supplier', p_supplier_id);
    RETURN v_id;
END;
$$;
