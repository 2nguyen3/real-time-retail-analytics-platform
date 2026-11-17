-- Run in the same psql session after seed_dimensions.py creates and fills stage06_dimension_input.
INSERT INTO stores (store_id, store_region)
SELECT store_id, MAX(store_region) FROM stage06_dimension_input GROUP BY store_id
ON CONFLICT (store_id) DO UPDATE
SET store_region = COALESCE(stores.store_region, EXCLUDED.store_region)
WHERE stores.store_region IS NULL AND EXCLUDED.store_region IS NOT NULL;

INSERT INTO products (product_id, category_id)
SELECT product_id, MAX(category_id) FROM stage06_dimension_input GROUP BY product_id
ON CONFLICT (product_id) DO UPDATE
SET category_id = COALESCE(products.category_id, EXCLUDED.category_id)
WHERE products.category_id IS NULL AND EXCLUDED.category_id IS NOT NULL;
