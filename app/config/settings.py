"""Application configuration and file system paths."""

import os
from pathlib import Path

# Application branding
APP_NAME = "Water Business Manager"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Water Business Solutions"

# Persistent User Data Directory: %LOCALAPPDATA%\WaterBusinessManager
if os.name == "nt":
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    BASE_USER_DIR = Path(local_app_data) / "WaterBusinessManager"
else:
    BASE_USER_DIR = Path.home() / ".water_business_manager"

DATA_DIR = BASE_USER_DIR / "data"
LOG_DIR = BASE_USER_DIR / "logs"
BACKUP_DIR = BASE_USER_DIR / "backups"
EXPORTS_DIR = BASE_USER_DIR / "exports"

# Create directories
for d in (DATA_DIR, LOG_DIR, BACKUP_DIR, EXPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Database file path (configurable via env var for testing / portable mode)
DEFAULT_DB_FILE = DATA_DIR / "business.db"
DB_PATH = Path(os.environ.get("WATER_DB_PATH", str(DEFAULT_DB_FILE)))

# Project base path (for assets, templates, migrations)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = PROJECT_ROOT / "app" / "assets"
TEMPLATES_DIR = PROJECT_ROOT / "app" / "reports" / "templates"
