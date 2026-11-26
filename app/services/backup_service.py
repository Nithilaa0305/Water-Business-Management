"""Database backup and restore service with transactional validation."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.config.settings import DB_PATH, BACKUP_DIR
from app.database.connection import backup_database_file, check_database_integrity, get_db_session, get_engine
from app.database.models.auth import BusinessProfile
from app.utilities.dates import now_colombo
from app.utilities.logger import logger


class BackupService:
    @staticmethod
    def get_configured_backup_dir(session=None) -> Path:
        """Get the configured backup directory or fallback to default BACKUP_DIR."""
        try:
            if session:
                prof = session.query(BusinessProfile).first()
                if prof and prof.backup_folder and prof.backup_folder.strip():
                    p = Path(prof.backup_folder.strip())
                    p.mkdir(parents=True, exist_ok=True)
                    return p
            else:
                with get_db_session() as s:
                    prof = s.query(BusinessProfile).first()
                    if prof and prof.backup_folder and prof.backup_folder.strip():
                        p = Path(prof.backup_folder.strip())
                        p.mkdir(parents=True, exist_ok=True)
                        return p
        except Exception as e:
            logger.warning(f"Could not load custom backup folder: {e}")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        return BACKUP_DIR

    @staticmethod
    def create_backup(destination_dir: Optional[Path] = None, custom_name: Optional[str] = None) -> Path:
        """
        Create a transactionally consistent online backup of the SQLite database.
        Never simply copies an uncheckpointed file.
        """
        target_dir = Path(destination_dir) if destination_dir else BackupService.get_configured_backup_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = now_colombo().strftime("%Y%m%d_%H%M%S")
        filename = custom_name or f"water_business_backup_{timestamp_str}.db"
        dest_file = target_dir / filename

        success = backup_database_file(source_path=DB_PATH, destination_path=dest_file)
        if not success:
            raise RuntimeError(f"Failed to create database backup at {dest_file}")

        # Verify backup integrity
        if not check_database_integrity(dest_file):
            if dest_file.exists():
                dest_file.unlink()
            raise RuntimeError("Backup file created but failed SQLite integrity check.")

        logger.info(f"Verified backup created at: {dest_file}")
        return dest_file

    @staticmethod
    def list_backups(target_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        """List all valid database backups sorted newest first."""
        d = Path(target_dir) if target_dir else BackupService.get_configured_backup_dir()
        if not d.exists():
            return []

        backups = []
        for f in d.glob("*.db"):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "path": str(f.resolve()),
                "size_bytes": stat.st_size,
                "size_mb": f"{stat.st_size / (1024 * 1024):.2f} MB",
                "modified_at": datetime.fromtimestamp(stat.st_mtime)
            })
        backups.sort(key=lambda x: x["modified_at"], reverse=True)
        return backups

    @staticmethod
    def restore_backup(backup_file_path: Path) -> bool:
        """
        Safely restore database from a backup:
        1. Validates backup file integrity.
        2. Creates safety backup of current live database.
        3. Disposes connection pools to release SQLite locks.
        4. Restores verified backup into live database location.
        """
        src = Path(backup_file_path)
        if not src.exists():
            raise FileNotFoundError(f"Backup file not found: {src}")

        if not check_database_integrity(src):
            raise ValueError("The selected backup file is corrupt or invalid. Restore aborted.")

        # Create safety backup of current database
        safety_dir = BACKUP_DIR / "safety_pre_restore"
        safety_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = now_colombo().strftime("%Y%m%d_%H%M%S")
        safety_file = safety_dir / f"safety_before_restore_{timestamp_str}.db"
        
        if DB_PATH.exists():
            backup_database_file(source_path=DB_PATH, destination_path=safety_file)
            logger.info(f"Created pre-restore safety backup at: {safety_file}")

        # Dispose connection pool to release all Windows file locks
        from app.database import connection
        if connection._engine is not None:
            connection._engine.dispose()
            connection._engine = None
            connection._SessionFactory = None

        # Restore from backup file into live DB_PATH
        success = backup_database_file(source_path=src, destination_path=DB_PATH)
        if not success:
            raise RuntimeError("Failed to restore backup file into production location.")

        logger.info(f"Database successfully restored from {src}")
        return True
