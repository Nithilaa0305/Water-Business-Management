-- 13: bills, customer account, payments, containers, expenses, supplier payments
CREATE SEQUENCE sale_number_seq;

CREATE TABLE sales (
    sale_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sale_number varchar(30) NOT NULL UNIQUE
        DEFAULT ('INV-' || lpad(nextval('sale_number_seq')::text, 6, '0')),
    customer_id uuid NOT NULL REFERENCES customers(customer_id),
    sale_date date NOT NULL DEFAULT CURRENT_DATE,
    subtotal numeric(14,2) NOT NULL DEFAULT 0,
    discount numeric(14,2) NOT NULL DEFAULT 0,
    total numeric(14,2) NOT NULL DEFAULT 0,
    amount_paid numeric(14,2) NOT NULL DEFAULT 0,
    status varchar(20) NOT NULL DEFAULT 'completed',
    notes text,
    created_by uuid NOT NULL REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    cancelled_by uuid REFERENCES app_users(user_id),
    cancelled_at timestamptz,
    cancel_reason text,
    CONSTRAINT chk_sale_status CHECK (status IN ('completed', 'cancelled')),
    CONSTRAINT chk_sale_discount CHECK (discount >= 0),
    CONSTRAINT chk_sale_total CHECK (total >= 0)
);

CREATE TABLE sale_items (
    sale_item_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sale_id uuid NOT NULL REFERENCES sales(sale_id),
    type_id uuid NOT NULL REFERENCES product_types(type_id),
    batch_id uuid NOT NULL REFERENCES stock_batches(batch_id),
    quantity integer NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    buying_price numeric(12,2) NOT NULL,
    returned_quantity integer NOT NULL DEFAULT 0,
    line_total numeric(14,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    CONSTRAINT chk_sale_item_quantity CHECK (quantity > 0),
    CONSTRAINT chk_sale_item_price CHECK (unit_price >= 0),
    CONSTRAINT chk_sale_item_returned CHECK (returned_quantity >= 0 AND returned_quantity <= quantity)
);

CREATE TABLE sale_returns (
    return_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    sale_id uuid NOT NULL REFERENCES sales(sale_id),
    sale_item_id uuid NOT NULL REFERENCES sale_items(sale_item_id),
    customer_id uuid NOT NULL REFERENCES customers(customer_id),
    quantity integer NOT NULL,
    credit_amount numeric(14,2) NOT NULL,
    cost_amount numeric(14,2) NOT NULL,
    reason text NOT NULL,
    returned_by uuid NOT NULL REFERENCES app_users(user_id),
    returned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_return_quantity CHECK (quantity > 0)
);

CREATE TABLE customer_ledger (
    ledger_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    customer_id uuid NOT NULL REFERENCES customers(customer_id),
    entry_time timestamptz NOT NULL DEFAULT clock_timestamp(),
    entry_type varchar(20) NOT NULL,
    reference_type varchar(50),
    reference_id uuid,
    debit numeric(14,2) NOT NULL DEFAULT 0,      -- customer owes more
    credit numeric(14,2) NOT NULL DEFAULT 0,     -- customer owes less
    running_balance numeric(14,2) NOT NULL,
    note text,
    created_by uuid REFERENCES app_users(user_id),
    CONSTRAINT chk_ledger_type CHECK (entry_type IN ('sale', 'payment', 'sale_return', 'sale_cancelled', 'adjustment')),
    CONSTRAINT chk_ledger_amounts CHECK (debit >= 0 AND credit >= 0)
);

CREATE TABLE payments (
    payment_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    customer_id uuid NOT NULL REFERENCES customers(customer_id),
    sale_id uuid REFERENCES sales(sale_id),
    payment_date date NOT NULL DEFAULT CURRENT_DATE,
    amount numeric(14,2) NOT NULL,
    method_id uuid REFERENCES payment_methods(method_id),
    notes text,
    received_by uuid NOT NULL REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_payment_amount CHECK (amount > 0)
);

CREATE TABLE container_movements (
    movement_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    customer_id uuid NOT NULL REFERENCES customers(customer_id),
    type_id uuid NOT NULL REFERENCES product_types(type_id),
    sale_id uuid REFERENCES sales(sale_id),
    movement_date date NOT NULL DEFAULT CURRENT_DATE,
    given_qty integer NOT NULL DEFAULT 0,
    returned_qty integer NOT NULL DEFAULT 0,
    notes text,
    created_by uuid NOT NULL REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_container_qty CHECK (given_qty >= 0 AND returned_qty >= 0 AND given_qty + returned_qty > 0)
);

CREATE TABLE customer_containers (
    customer_id uuid NOT NULL REFERENCES customers(customer_id),
    type_id uuid NOT NULL REFERENCES product_types(type_id),
    held integer NOT NULL DEFAULT 0,
    PRIMARY KEY (customer_id, type_id),
    CONSTRAINT chk_container_held CHECK (held >= 0)
);

CREATE TABLE expenses (
    expense_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    expense_date date NOT NULL DEFAULT CURRENT_DATE,
    expense_category_id uuid NOT NULL REFERENCES expense_categories(expense_category_id),
    amount numeric(14,2) NOT NULL,
    notes text,
    created_by uuid NOT NULL REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_expense_amount CHECK (amount > 0)
);

CREATE TABLE supplier_payments (
    supplier_payment_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    supplier_id uuid NOT NULL REFERENCES suppliers(supplier_id),
    payment_date date NOT NULL DEFAULT CURRENT_DATE,
    amount numeric(14,2) NOT NULL,
    method_id uuid REFERENCES payment_methods(method_id),
    notes text,
    created_by uuid NOT NULL REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_supplier_payment_amount CHECK (amount > 0)
);
