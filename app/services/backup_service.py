"""Service for database backup and restore operations."""
import os
from app.utils.timeutils import utcnow
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException


class BackupService:
    """Service for managing database backups and restores."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.backup_dir = Path("data/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///./", ""))

    async def create_backup(self, name: Optional[str] = None) -> dict:
        """
        Create a complete backup of the database and uploaded files.

        Returns:
            dict: Backup metadata including filename, size, and path
        """
        timestamp = utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"backup_{timestamp}"
        backup_filename = f"{backup_name}.zip"
        backup_path = self.backup_dir / backup_filename

        try:
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Backup database file
                if self.db_path.exists():
                    zipf.write(self.db_path, "database.db")

                # Backup uploaded files
                files_dir = Path(settings.LOCAL_STORAGE_PATH)
                if files_dir.exists():
                    for file_path in files_dir.rglob("*"):
                        if file_path.is_file():
                            arcname = f"files/{file_path.relative_to(files_dir)}"
                            zipf.write(file_path, arcname)

                # Add metadata
                metadata = {
                    "created_at": utcnow().isoformat(),
                    "app_version": settings.APP_VERSION,
                    "backup_name": backup_name,
                }
                zipf.writestr("metadata.json", json.dumps(metadata, indent=2))

            # Get backup file size
            backup_size = backup_path.stat().st_size

            return {
                "filename": backup_filename,
                "name": backup_name,
                "size": backup_size,
                "size_mb": round(backup_size / (1024 * 1024), 2),
                "created": utcnow().isoformat(),
                "path": str(backup_path),
            }

        except Exception as e:
            # Clean up failed backup
            if backup_path.exists():
                backup_path.unlink()
            raise BadRequestException(f"Failed to create backup: {str(e)}")

    async def list_backups(self) -> List[dict]:
        """
        List all available backups.

        Returns:
            List of backup metadata
        """
        backups = []

        for backup_file in self.backup_dir.glob("*.zip"):
            try:
                # Get file stats
                stat = backup_file.stat()
                size = stat.st_size
                created = datetime.fromtimestamp(stat.st_mtime)

                # Try to read metadata from zip
                metadata = {}
                try:
                    with zipfile.ZipFile(backup_file, "r") as zipf:
                        if "metadata.json" in zipf.namelist():
                            metadata = json.loads(zipf.read("metadata.json"))
                except Exception:
                    pass

                backups.append(
                    {
                        "filename": backup_file.name,
                        "name": backup_file.stem,
                        "size": size,
                        "size_mb": round(size / (1024 * 1024), 2),
                        "created": metadata.get("created_at", created.isoformat()),
                        "app_version": metadata.get("app_version", "unknown"),
                    }
                )
            except Exception:
                continue

        # Sort by creation time, newest first
        backups.sort(key=lambda x: x["created"], reverse=True)
        return backups

    async def restore_backup(self, filename: str) -> dict:
        """
        Prepare backup for restoration on next server restart.

        This creates a staging area and marker file. The actual restore
        happens on server startup to avoid database lock issues.

        Args:
            filename: Name of the backup file to restore

        Returns:
            dict: Restoration status and metadata
        """
        backup_path = self.backup_dir / filename

        if not backup_path.exists():
            raise NotFoundException(f"Backup file '{filename}' not found")

        try:
            # Create restore staging directory
            restore_staging = self.backup_dir / "restore_staging"
            if restore_staging.exists():
                shutil.rmtree(restore_staging)
            restore_staging.mkdir(exist_ok=True)

            # Extract backup to staging
            with zipfile.ZipFile(backup_path, "r") as zipf:
                zipf.extractall(restore_staging)

            # Create marker file with restore metadata
            marker_file = self.backup_dir / ".restore_pending"
            marker_data = {
                "backup_filename": filename,
                "requested_at": utcnow().isoformat(),
                "staging_path": str(restore_staging),
            }
            marker_file.write_text(json.dumps(marker_data, indent=2))

            return {
                "status": "pending_restart",
                "message": f"Backup '{filename}' staged for restore. Please restart the server to complete restoration.",
                "backup_filename": filename,
                "requested_at": marker_data["requested_at"],
            }

        except Exception as e:
            # Clean up on failure
            restore_staging = self.backup_dir / "restore_staging"
            if restore_staging.exists():
                shutil.rmtree(restore_staging)

            marker_file = self.backup_dir / ".restore_pending"
            if marker_file.exists():
                marker_file.unlink()

            raise BadRequestException(f"Failed to prepare backup for restore: {str(e)}")

    @staticmethod
    def perform_restore_on_startup() -> bool:
        """
        Check for pending restore and perform it if found.
        This should be called during app startup BEFORE initializing the database.

        Returns:
            bool: True if restore was performed, False otherwise
        """
        backup_dir = Path("data/backups")
        marker_file = backup_dir / ".restore_pending"

        if not marker_file.exists():
            return False

        try:
            # Read marker file
            marker_data = json.loads(marker_file.read_text())
            restore_staging = Path(marker_data["staging_path"])

            if not restore_staging.exists():
                marker_file.unlink()
                return False

            # Get database path
            db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///./", ""))

            # Backup current database
            if db_path.exists():
                backup_path = db_path.with_suffix(".db.before_restore")
                shutil.copy2(db_path, backup_path)

            # Restore database
            db_backup = restore_staging / "database.db"
            if db_backup.exists():
                shutil.copy2(db_backup, db_path)

            # Restore files
            files_backup = restore_staging / "files"
            if files_backup.exists():
                files_dir = Path(settings.LOCAL_STORAGE_PATH)

                # Backup current files
                if files_dir.exists():
                    current_files_backup = files_dir.parent / f"{files_dir.name}_before_restore"
                    if current_files_backup.exists():
                        shutil.rmtree(current_files_backup)
                    shutil.copytree(files_dir, current_files_backup)
                    shutil.rmtree(files_dir)

                # Restore from backup
                shutil.copytree(files_backup, files_dir)

            # Clean up
            shutil.rmtree(restore_staging)
            marker_file.unlink()

            return True

        except Exception as e:
            # Log error but don't fail startup
            print(f"Failed to restore backup on startup: {str(e)}")
            # Clean up marker to avoid infinite loop
            if marker_file.exists():
                marker_file.unlink()
            return False

    async def delete_backup(self, filename: str) -> None:
        """
        Delete a backup file.

        Args:
            filename: Name of the backup file to delete
        """
        backup_path = self.backup_dir / filename

        if not backup_path.exists():
            raise NotFoundException(f"Backup file '{filename}' not found")

        try:
            backup_path.unlink()
        except Exception as e:
            raise BadRequestException(f"Failed to delete backup: {str(e)}")

    async def download_backup(self, filename: str) -> Path:
        """
        Get path to a backup file for download.

        Args:
            filename: Name of the backup file

        Returns:
            Path to the backup file
        """
        backup_path = self.backup_dir / filename

        if not backup_path.exists():
            raise NotFoundException(f"Backup file '{filename}' not found")

        return backup_path
