-- 05: customers and suppliers
CREATE TABLE customers (
    customer_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    customer_name varchar(200) NOT NULL,
    phone varchar(30),
    address text,
    area_id uuid REFERENCES areas(area_id),
    credit_limit numeric(12,2) NOT NULL DEFAULT 0,
    balance numeric(14,2) NOT NULL DEFAULT 0,   -- positive = customer owes you, negative = you owe customer
    notes text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_customer_credit_limit CHECK (credit_limit >= 0)
);

CREATE TABLE suppliers (
    supplier_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    supplier_name varchar(200) NOT NULL,
    phone varchar(30),
    address text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
