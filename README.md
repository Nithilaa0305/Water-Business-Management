# Wholesale Water Billing

This version uses React/Vite with an Express server and a local SQLite database. It imports the app from `thivi400/inventory-billing` at `d096e26960821440aa687420b6df6cb632c6d342`. Node.js 22.13+ is required at runtime; Bun is used to install the locked dependencies. The prior FastAPI/PostgreSQL implementation remains available in Git history; this version **does not import or migrate its data**.

## Run a disposable trial

With Node.js 22 and Bun installed:

```sh
bun install --frozen-lockfile
npm run lint
npm run build
```

For a production-mode trial on Windows PowerShell, use a new SQLite path distinct from all shop data:

```powershell
$env:DB_PATH = Join-Path $env:TEMP ("billing-trial-" + [guid]::NewGuid() + ".sqlite")
$env:NODE_ENV = "production"
npm start
```

Open `http://127.0.0.1:3000`. Use **Load Sample Trial Shop** only in the disposable database. Production mode serves the existing `dist/` build and binds to loopback by default. `npm run dev` starts the development server; use a disposable `DB_PATH` for it as well. Preserve any existing PostgreSQL or SQLite backups; do not point this app or a trial at an existing shop database.

## Verification

```sh
npx --no-install tsx scripts/verify-all-gates.ts
```

The API verification script creates its own temporary SQLite database regardless of `DB_PATH`. It never uses the app's data file. These are Linux/Node and SQLite checks, not Windows installer, physical printer, backup/restore, or production migration tests. `docs/SPEC.md` is the project's requirements reference, not a claim that the imported version implements every item.
