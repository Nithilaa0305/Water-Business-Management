# Offline Windows handover — installer checklist

This is a technician runbook, not a redistributable installer. The seller uses only the **Wholesale Billing** desktop shortcut after setup. Do not reuse a demo database, PIN, or configuration. Nothing in `start.bat` creates, seeds, or migrates a database.

## Prepare the release on a staging computer

1. Start from an approved commit. Record its hash and the Windows, PostgreSQL, Python, and Node versions. Run `npm ci`, `npm run typecheck`, and `npm run build` from `frontend` using Node 22. Copy `.env.example` to `.env.production.local` before building for the shop. Enter the shop's actual English/Tamil name and applicable contact/tax details. Leave `VITE_API_URL` empty. Check that no credentials are in the frontend files. Fonts are bundled; no CDN is needed.
2. Stage the Windows x64 installers for PostgreSQL (with command-line tools, including `psql`, `pg_dump`, and `pg_restore`) and Python. On a matching Windows build machine, resolve `backend/requirements.txt` in a fresh venv, `pip freeze` to the release's Windows lock file, and use `pip download --only-binary=:all: -r <lock-file> -d wheelhouse`. Smoke-test an install using only this wheelhouse. Include the lock file and versions/checksums with the private handover materials, not a venv copied from another computer.
3. Copy app source, `frontend/dist`, `database`, `install.sql`, `setup`, and `start.bat` to the client bundle. Exclude `.git`, test data, `.env` files, logs, dumps, and `node_modules`.

## Set up the shop once

1. Install PostgreSQL as a Windows service set to Automatic. Restrict it to loopback and password authentication. Use `psql -l` / `Get-Service *postgres*` to verify the intended **local** instance. Create a new login limited to this app database (not a superuser) and a new UTF-8 database such as `billing_shop`, owned by that role. Assign the database password using the administrator's local tooling; never put passwords on command lines. Ensure the PostgreSQL `pgcrypto` extension is available. Keep the DB admin login separate from the owner's app PIN.
2. From the application root, install the schema into the new database only:

   ```powershell
   psql -h 127.0.0.1 -U billing_app -d billing_shop -v ON_ERROR_STOP=1 -f install.sql
   # Optional: SIX unpriced, zero-stock products, and no sample records.
   psql -h 127.0.0.1 -U billing_app -d billing_shop -v ON_ERROR_STOP=1 -f setup/seed_catalog.sql
   ```

   If the role cannot install `pgcrypto`, use the local administrator to enable it in that database before continuing. For an existing shop schema at module 19, do **not** rerun `install.sql`: review module 20, take a verified backup, and test it on a restored copy first. Apply to a shop database only after explicit approval and with the sellers signed out.
3. Create the venv and install dependencies without the internet:

   ```powershell
   py -3.11 -m venv backend\venv
   .\backend\venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r .\requirements-windows.lock
   ```

   Create `backend/.env` from its example. Set the **new** database URL with the app role and a new random `SECRET_KEY` (generate once using `python -c "import secrets; print(secrets.token_hex(32))"` on the client). URL-encode the login/password if needed. Restrict the file to the local Windows user/service and administrators; do not commit it. Use `SHOP_TIMEZONE=Asia/Colombo`.
4. Run `backend\venv\Scripts\python.exe setup\create_owner.py`. Confirm the DB name on screen; the real owner chooses the PIN privately. Set real prices before receiving/billing items. Create staff accounts with role-appropriate permissions.
5. Create a desktop shortcut to `start.bat`, name it **Wholesale Billing**, and keep the app folder at a fixed location. The launcher checks for the Python venv and built frontend, starts the loopback FastAPI process if needed, and opens the browser after it responds. It relies on PostgreSQL already running as a Windows service. Node and internet are not required at runtime. Do not expose port 8000 to the network.

## Backup, restore, and acceptance

- While Windows is offline, cold boot, use only the shortcut, sign in as owner and employee, then close/reopen and reboot. Verify actual data in the separate acceptance database survives. Check the EN/TA labels and local fonts; Windows speech needs an installed local voice and may be unavailable in Tamil.
- Post a disposable fixture invoice, including partial tender/old debt and a can return. Confirm Stock, customer ledger, Home, Reports, and invoice history reconcile. Print both A4 and 80 mm on the **actual printer/driver** with headers/footers disabled, and check a long itemized bill. Download each format separately; the browser should not open the print dialog for Download PDF. Check the full invoice number, Tamil glyphs, and totals against the saved invoice.
- Schedule daily backups under a dedicated local account and record the exit status. With a dedicated restricted destination (choose an actual removable/encrypted backup path), the technician can run:

   ```powershell
   pg_dump -h 127.0.0.1 -U billing_app -d billing_shop -Fc -f E:\BillingBackups\billing-YYYY-MM-DD.dump
   pg_restore --list E:\BillingBackups\billing-YYYY-MM-DD.dump
   # First create a separate empty billing_restore_check database. NEVER restore over the shop during a drill.
   pg_restore -h 127.0.0.1 -U billing_app -d billing_restore_check --exit-on-error --no-owner E:\BillingBackups\billing-YYYY-MM-DD.dump
   ```

   Rotate media; keep at least one copy off the PC. `pg_restore --list` isn't a restore test. On the restored DB, compare recent invoices, counts, stock and balance totals with the source snapshot, and open a saved receipt in a separate app instance. Keep local config recovery instructions separate from the dump; a new JWT secret invalidates sessions, not invoices. For rollback after new sales, stop writes and reconcile them **before** considering restoration; restoring a pre-upgrade dump discards later sales.

## Decisions not automated by this release

- Goods returns credit the customer account; they do not issue a cash refund. Tick **Put sellable goods back into stock** only after inspection. Paid invoices and invoices with can movements cannot be cancelled from the simple cancellation action. Agree on a cash-refund/reconciliation policy before enabling one.
- The filled SKU and the sellable new empty SKU are different stock batches. Returned used cans reduce the customer's held count; they do **not** increase sellable new cans. Decide how to count returnables in the shop (used/clean/refill/damaged) before posting to a physical inventory. Do not add returned cans as new sellable cans as a workaround.
- Module 20 does not backfill snapshots, costs, void timestamps, or physical movements that weren't stored historically. Historic invoice details are reconstructed from available rows and can reflect catalog names current at lookup. Check migrated books against a copy before authorizing use.

## Repeatable sandbox regression

Use a new disposable UTF-8 database with a name ending `_test`, never a shop DB. Install `backend/requirements.txt` and `httpx` into a dev venv, set `TEST_DATABASE_URL` to that disposable database, and run `python tests/test_operational_integrity.py` from the repository root. The suite installs all numbered modules and uses its own synthetic users and transactions. It refuses initialized schemas. On Python 3.11 in this workspace, the test runner is `.venv/bin/python`.

For browser regression, serve the built frontend and FastAPI at `127.0.0.1:18000` with `DATABASE_URL` explicitly pointing to the initialized regression DB (use `BILLING_PORT=18000` and a fresh secret). Install `playwright-core` in a separate tools folder, set `NODE_PATH` to that folder's `node_modules`, and set `CHROMIUM_EXECUTABLE` to a local Chromium executable. Run `node tests/browser_operational_integrity.cjs`. The harness signs in as the regression owner, creates synthetic browser fixtures, and deliberately drops responses after the server receives them. Never point this runner at a shop instance.

**Sandbox verification:** PostgreSQL 16.2 `pg_dump`/`pg_restore` restored a disposable full-schema database to a separate empty DB. Sales and receipt snapshots, stock, balances, ledger totals, payments, held cans, and retry state matched, and FastAPI reopened the saved invoice on the restored DB. Module 20 was also applied twice to a populated synthetic module-19 schema without rewriting the existing transaction rows. These checks do not replace the Windows restore, disconnected reboot, and printer drills above.
