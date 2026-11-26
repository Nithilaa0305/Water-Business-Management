"""Application Entry Point for Water Business Manager."""

import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from app.config.settings import APP_NAME, APP_VERSION, APP_AUTHOR, DB_PATH
from app.database.connection import get_engine, check_database_integrity
from app.database.migrations.migration_manager import init_database
from app.ui.main_window import MainWindow
from app.ui.theme import apply_app_theme
from app.utilities.logger import logger


def ensure_single_instance(app_id: str = "WaterBusinessManagerSingleInstanceLock"):
    """Prevent multiple instances from accidentally corrupting the local SQLite database."""
    socket = QLocalSocket()
    socket.connectToServer(app_id)
    if socket.waitForConnected(500):
        # An instance is already running
        return None
    server = QLocalServer()
    # Remove stale socket if present
    QLocalServer.removeServer(app_id)
    if not server.listen(app_id):
        logger.warning("Could not create single-instance socket server.")
    return server


def main():
    # Enable High DPI scaling
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_AUTHOR)

    # Apply unified light theme and high-contrast palette across entire application
    apply_app_theme(app)

    # Single instance check
    instance_server = ensure_single_instance()
    if instance_server is None:
        QMessageBox.warning(
            None,
            "Already Running",
            "Water Business Manager is already open and running on this computer.\n"
            "Only one active instance can be open at a time to protect your database."
        )
        sys.exit(0)

    try:
        # Initialize database and default master data
        engine = get_engine()
        init_database(engine, seed_defaults=True)
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Database Initialization Error",
            f"Unable to initialize local database at:\n{DB_PATH}\n\nTechnical details:\n{str(e)}"
        )
        sys.exit(1)

    # Create and display Main Window in full screen / maximized view
    window = MainWindow()
    window.showMaximized()

    # Trigger first-time setup wizard if needed
    window.check_first_time_setup()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
