-- 06: stock batches, stock ledger and price history
CREATE SEQUENCE batch_number_seq;

CREATE TABLE stock_batches (
    batch_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    batch_number varchar(30) NOT NULL UNIQUE
        DEFAULT ('B-' || lpad(nextval('batch_number_seq')::text, 6, '0')),
    type_id uuid NOT NULL REFERENCES product_types(type_id),
    supplier_id uuid REFERENCES suppliers(supplier_id),
    supplier_invoice_no varchar(50),
    quantity_received integer NOT NULL,
    current_quantity integer NOT NULL,
    buying_price numeric(12,2) NOT NULL,
    selling_price numeric(12,2),
    expiry_date date,
    received_date date NOT NULL DEFAULT CURRENT_DATE,
    created_by uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_batch_quantity_received CHECK (quantity_received > 0),
    CONSTRAINT chk_batch_current_quantity CHECK (current_quantity >= 0),
    CONSTRAINT chk_batch_buying_price CHECK (buying_price >= 0),
    CONSTRAINT chk_batch_selling_price CHECK (selling_price IS NULL OR selling_price >= 0)
);

CREATE TABLE inventory_transactions (
    transaction_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    batch_id uuid NOT NULL REFERENCES stock_batches(batch_id),
    transaction_type varchar(30) NOT NULL,
    quantity integer NOT NULL,
    quantity_change integer NOT NULL,
    transaction_date timestamptz NOT NULL DEFAULT clock_timestamp(),
    reference_type varchar(50),
    reference_id uuid,
    reference_note text,
    created_by uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_inventory_quantity CHECK (quantity > 0),
    CONSTRAINT chk_inventory_quantity_change CHECK (quantity_change <> 0),
    CONSTRAINT chk_inventory_type CHECK (transaction_type IN
        ('stock_received', 'sold', 'sale_return', 'sale_cancelled', 'expired', 'damaged', 'adjustment'))
);

CREATE TABLE price_history (
    price_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    type_id uuid NOT NULL REFERENCES product_types(type_id),
    batch_id uuid REFERENCES stock_batches(batch_id),
    price_kind varchar(10) NOT NULL,
    old_price numeric(12,2),
    new_price numeric(12,2) NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    changed_by uuid REFERENCES app_users(user_id),
    note text,
    CONSTRAINT chk_price_kind CHECK (price_kind IN ('buying', 'selling')),
    CONSTRAINT chk_price_new CHECK (new_price >= 0)
);
