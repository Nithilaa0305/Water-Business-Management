-- 04: products and their types
CREATE TABLE products (
    product_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    category_id uuid REFERENCES categories(category_id),
    product_name varchar(200) NOT NULL UNIQUE,
    description text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE product_types (
    type_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    product_id uuid NOT NULL REFERENCES products(product_id),
    type_name varchar(150) NOT NULL,
    sku varchar(50) UNIQUE,
    unit_id uuid REFERENCES units(unit_id),
    low_stock_limit integer NOT NULL DEFAULT 0,
    default_selling_price numeric(12,2) NOT NULL DEFAULT 0,
    is_returnable_container boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_type UNIQUE (product_id, type_name),
    CONSTRAINT chk_type_low_stock CHECK (low_stock_limit >= 0),
    CONSTRAINT chk_type_default_price CHECK (default_selling_price >= 0)
);
