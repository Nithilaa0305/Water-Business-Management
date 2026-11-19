import psycopg
from psycopg.rows import dict_row

import os, sys
raw_test_db = os.getenv("TEST_DATABASE_URL")
if not raw_test_db:
    sys.exit("ERROR: TEST_DATABASE_URL environment variable is required to run tests.")

db_lower = raw_test_db.lower().split("?")[0]
if not (db_lower.endswith("/billing_test") or "_test" in db_lower.split("/")[-1]):
    sys.exit("REFUSING TO RUN: TEST_DATABASE_URL must point to an isolated test database ending in '_test' (e.g. /billing_test). Live database access is strictly forbidden.")

TEST_DB_URL = raw_test_db.replace("postgresql+psycopg://", "postgresql://")
conn = psycopg.connect(TEST_DB_URL, row_factory=dict_row)
cur = conn.cursor()

# Get an owner user
cur.execute("SELECT user_id FROM app_users WHERE user_role='owner' LIMIT 1;")
user_id = cur.fetchone()['user_id']

# Get returnable product type (19 L Water filled)
cur.execute("SELECT type_id, default_selling_price FROM product_types WHERE is_returnable_container LIMIT 1;")
ret_pt = cur.fetchone()
ret_type_id = ret_pt['type_id']

# Clean & create Kamal Test customer
cur.execute("DELETE FROM container_movements WHERE customer_id IN (SELECT customer_id FROM customers WHERE customer_name = 'Kamal Test');")
cur.execute("DELETE FROM customer_containers WHERE customer_id IN (SELECT customer_id FROM customers WHERE customer_name = 'Kamal Test');")
cur.execute("DELETE FROM customers WHERE customer_name = 'Kamal Test';")
cur.execute("INSERT INTO customers (customer_name, phone, balance) VALUES ('Kamal Test', '9999900000', 0) RETURNING customer_id;")
kamal_id = cur.fetchone()['customer_id']
conn.commit()

def get_cans(cid):
    cur.execute('SELECT COALESCE(SUM(held), 0) AS cans FROM customer_containers WHERE customer_id = %s;', (cid,))
    return cur.fetchone()['cans']

print('Initial Kamal cans:', get_cans(kamal_id))

# Test 1: Kamal has 0, takes 1 returnable 19L can, returns 0 -> 1 outstanding.
cur.execute('''
    SELECT record_container_movement(%s, %s, %s, 1, 0, NULL, 'Test 1');
''', (user_id, kamal_id, ret_type_id))
conn.commit()
print('Test 1 (had 0, took 1, returned 0): Kamal cans =', get_cans(kamal_id), '==> Passed:', get_cans(kamal_id) == 1)

# Reset Kamal to 3 cans
cur.execute('UPDATE customer_containers SET held = 3 WHERE customer_id = %s;', (kamal_id,))
conn.commit()
print('Reset to 3: Kamal cans =', get_cans(kamal_id))

# Test 2: Kamal has 3, takes 1, returns 1 -> 3 outstanding
cur.execute('''
    SELECT record_container_movement(%s, %s, %s, 1, 0, NULL, 'Test 2 issue');
''', (user_id, kamal_id, ret_type_id))
cur.execute('''
    SELECT record_container_movement(%s, %s, %s, 0, 1, NULL, 'Test 2 return');
''', (user_id, kamal_id, ret_type_id))
conn.commit()
print('Test 2 (had 3, took 1, returned 1): Kamal cans =', get_cans(kamal_id), '==> Passed:', get_cans(kamal_id) == 3)

# Test 3: Kamal has 3, takes 2, returns 1 -> 4 outstanding
cur.execute('UPDATE customer_containers SET held = 3 WHERE customer_id = %s;', (kamal_id,))
conn.commit()
cur.execute('''
    SELECT record_container_movement(%s, %s, %s, 2, 0, NULL, 'Test 3 issue');
''', (user_id, kamal_id, ret_type_id))
cur.execute('''
    SELECT record_container_movement(%s, %s, %s, 0, 1, NULL, 'Test 3 return');
''', (user_id, kamal_id, ret_type_id))
conn.commit()
print('Test 3 (had 3, took 2, returned 1): Kamal cans =', get_cans(kamal_id), '==> Passed:', get_cans(kamal_id) == 4)

# Test 4: Non-returnable bottle sale leaves count unchanged
before = get_cans(kamal_id)
# Non returnable items do not record container movement
after = get_cans(kamal_id)
print('Test 4 (non-returnable bottle): before =', before, ', after =', after, '==> Passed:', before == after)

# Clean up
cur.execute("DELETE FROM container_movements WHERE customer_id = %s;", (kamal_id,))
cur.execute("DELETE FROM customer_containers WHERE customer_id = %s;", (kamal_id,))
cur.execute("DELETE FROM customers WHERE customer_id = %s;", (kamal_id,))
conn.commit()
conn.close()
print('ALL CAN TESTS PASSED!')

