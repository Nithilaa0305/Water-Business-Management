-- 01: drop-down lists the user can edit
CREATE TABLE units (
    unit_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    unit_name varchar(50) NOT NULL UNIQUE,
    is_active boolean NOT NULL DEFAULT true
);
CREATE TABLE categories (
    category_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    category_name varchar(100) NOT NULL UNIQUE,
    is_active boolean NOT NULL DEFAULT true
);
CREATE TABLE areas (
    area_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    area_name varchar(100) NOT NULL UNIQUE,
    is_active boolean NOT NULL DEFAULT true
);
CREATE TABLE payment_methods (
    method_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    method_name varchar(50) NOT NULL UNIQUE,
    is_active boolean NOT NULL DEFAULT true
);
CREATE TABLE expense_categories (
    expense_category_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    expense_category_name varchar(100) NOT NULL UNIQUE,
    is_active boolean NOT NULL DEFAULT true
);

INSERT INTO units (unit_name) VALUES ('piece'), ('bottle'), ('can'), ('case'), ('pack'), ('kg'), ('litre');
INSERT INTO payment_methods (method_name) VALUES ('Cash'), ('Bank Transfer'), ('Cheque'), ('Card'), ('Other');
INSERT INTO expense_categories (expense_category_name) VALUES ('Fuel'), ('Salary'), ('Rent'), ('Electricity'), ('Repairs'), ('Other');
