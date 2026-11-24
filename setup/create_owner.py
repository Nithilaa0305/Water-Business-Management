"""Installer-only first-owner setup; reads backend/.env and prompts for the PIN."""
import getpass
import re
from pathlib import Path

import psycopg
from dotenv import dotenv_values


def main():
    config = dotenv_values(Path(__file__).resolve().parents[1] / "backend" / ".env")
    url = config.get("DATABASE_URL")
    if not url:
        raise SystemExit("Configure backend/.env first.")
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://", 1)) as db:
        target = db.execute("SELECT current_database(), inet_server_addr(), inet_server_port()").fetchone()
        if str(target[1]) not in {"127.0.0.1", "::1"}:
            raise SystemExit("Owner setup requires a local PostgreSQL instance.")
        print(f"Database: {target[0]} at {target[1]} port {target[2]}")
        if input("Type that new database name to confirm: ").strip() != target[0]:
            raise SystemExit("Cancelled.")
        db.execute("LOCK TABLE app_users IN SHARE ROW EXCLUSIVE MODE")
        if db.execute("SELECT EXISTS (SELECT 1 FROM app_users)").fetchone()[0]:
            raise SystemExit("An owner already exists. Manage staff through the owner workflow.")
        name = input("Owner's name: ").strip()
        username = input("Owner's username: ").strip().lower()
        pin = getpass.getpass("Choose a private PIN (4 to 8 digits): ")
        if not name or not username or not re.fullmatch(r"[0-9]{4,8}", pin):
            raise SystemExit("Enter a name, username, and valid PIN.")
        if pin != getpass.getpass("Repeat the PIN: "):
            raise SystemExit("PINs do not match.")
        db.execute("SELECT create_user(%s,%s,%s,'owner')", (name, username, pin))
    print("Owner created. Keep the PIN private and sign in under Owner.")


if __name__ == "__main__":
    main()
