"""Backup and restore integration tests."""

import os
from pathlib import Path
from app.services.backup_service import BackupService
from app.database.connection import check_database_integrity, DB_PATH


def test_backup_creation_and_integrity(tmp_path):
    # Create backup in temporary path
    backup_file = BackupService.create_backup(destination_dir=tmp_path)
    assert backup_file.exists()
    assert backup_file.stat().st_size > 0
    assert check_database_integrity(backup_file) is True

    # List backups
    backups = BackupService.list_backups(target_dir=tmp_path)
    assert len(backups) >= 1
    assert backups[0]["filename"] == backup_file.name
