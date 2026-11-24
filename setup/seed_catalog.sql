-- Optional: run only for a new shop that uses these six products.
-- No prices, costs, customers, stock, or sales are created.
BEGIN;
LOCK TABLE products, product_types IN SHARE ROW EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM products) THEN
        RAISE EXCEPTION 'Starter catalog is for an empty catalog only';
    END IF;
END;
$$;
WITH water AS (
    INSERT INTO products (product_name) VALUES ('Drinking Water') RETURNING product_id
), starter(name, ta, sku, unit, returnable) AS (
    VALUES ('500 ml Water', '500 மிலி தண்ணீர்', 'SKU-500ML', 'bottle', false),
           ('1 L Water', '1 லிட்டர் தண்ணீர்', 'SKU-1L', 'bottle', false),
           ('1.5 L Water', '1.5 லிட்டர் தண்ணீர்', 'SKU-1.5L', 'bottle', false),
           ('5 L Water', '5 லிட்டர் தண்ணீர்', 'SKU-5L', 'can', false),
           ('19 L Water (filled)', '19 லிட்டர் நிரப்பப்பட்ட கேன்', 'SKU-19L', 'can', true),
           ('19 L Bottle (empty/new)', '19 லிட்டர் காலி கேன் (புதியது)', 'SKU-19L-EMPTY', 'can', false)
)
INSERT INTO product_types (product_id, type_name, tamil_name, sku, unit_id, is_returnable_container)
SELECT water.product_id, starter.name, starter.ta, starter.sku, units.unit_id, starter.returnable
FROM water CROSS JOIN starter JOIN units ON units.unit_name = starter.unit;
COMMIT;
