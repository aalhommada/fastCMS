"""Service for file upload, download, and management."""
import os
import uuid
import math
from pathlib import Path
from typing import Optional, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.file import FileRepository
from app.schemas.file import FileResponse, FileListResponse, FileUpload
from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ValidationException,
)


class FileService:
    """Service for managing file uploads and downloads."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FileRepository(db)
        self.storage_path = Path(settings.LOCAL_STORAGE_PATH)

        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def upload_file(
        self,
        file_content: BinaryIO,
        filename: str,
        mime_type: str,
        size: int,
        user_id: Optional[str] = None,
        metadata: Optional[FileUpload] = None,
    ) -> FileResponse:
        """Upload a file and store metadata."""
        # Validate file size
        if size > settings.MAX_FILE_SIZE:
            raise ValidationException(
                f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE} bytes"
            )

        # Validate MIME type
        if mime_type not in settings.ALLOWED_FILE_TYPES:
            raise ValidationException(
                f"File type '{mime_type}' is not allowed. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES)}"
            )

        # Generate unique filename
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"

        # Determine storage path
        relative_path = self._get_storage_path(unique_filename)
        full_path = self.storage_path / relative_path

        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file to disk
        try:
            with open(full_path, "wb") as f:
                f.write(file_content.read())
        except Exception as e:
            raise BadRequestException(f"Failed to save file: {str(e)}")

        # Create database record
        file_data = {
            "filename": unique_filename,
            "original_filename": filename,
            "mime_type": mime_type,
            "size": size,
            "storage_path": str(relative_path),
            "storage_type": settings.STORAGE_TYPE,
            "user_id": user_id,
        }

        if metadata:
            if metadata.collection_name:
                file_data["collection_name"] = metadata.collection_name
            if metadata.record_id:
                file_data["record_id"] = metadata.record_id
            if metadata.field_name:
                file_data["field_name"] = metadata.field_name

        file = await self.repo.create(file_data)
        await self.db.commit()

        return self._to_response(file)

    async def get_file(self, file_id: str) -> FileResponse:
        """Get file metadata by ID."""
        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        return self._to_response(file)

    async def get_file_content(self, file_id: str) -> tuple[Path, str, str]:
        """Get file content for download."""
        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        file_path = self.storage_path / file.storage_path

        if not file_path.exists():
            raise NotFoundException(f"File content not found on disk")

        return file_path, file.original_filename, file.mime_type

    async def list_files(
        self,
        page: int = 1,
        per_page: int = 20,
        collection_name: Optional[str] = None,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> FileListResponse:
        """List files with pagination and filtering."""
        skip = (page - 1) * per_page

        files = await self.repo.get_all(
            skip=skip,
            limit=per_page,
            collection_name=collection_name,
            record_id=record_id,
            user_id=user_id,
        )
        total = await self.repo.count(
            collection_name=collection_name,
            record_id=record_id,
            user_id=user_id,
        )

        items = [self._to_response(file) for file in files]
        total_pages = math.ceil(total / per_page) if total > 0 else 0

        return FileListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def delete_file(self, file_id: str) -> None:
        """Delete a file (soft delete in DB, physical delete on disk)."""
        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        # Soft delete in database
        await self.repo.soft_delete(file_id)

        # Delete physical file
        file_path = self.storage_path / file.storage_path
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                # Log error but don't fail the request
                pass

        # Delete thumbnails if any
        thumbnails = await self.repo.get_thumbnails(file_id)
        for thumb in thumbnails:
            thumb_path = self.storage_path / thumb.storage_path
            if thumb_path.exists():
                try:
                    thumb_path.unlink()
                except Exception:
                    pass
            await self.repo.soft_delete(thumb.id)

        await self.db.commit()

    def _get_storage_path(self, filename: str) -> str:
        """Generate storage path with date-based organization."""
        from datetime import datetime

        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")

        return f"{year}/{month}/{day}/{filename}"

    def _to_response(self, file) -> FileResponse:
        """Convert file model to response schema."""
        response = FileResponse(
            id=file.id,
            filename=file.filename,
            original_filename=file.original_filename,
            mime_type=file.mime_type,
            size=file.size,
            storage_path=file.storage_path,
            storage_type=file.storage_type,
            collection_name=file.collection_name,
            record_id=file.record_id,
            field_name=file.field_name,
            user_id=file.user_id,
            is_thumbnail=file.is_thumbnail,
            parent_file_id=file.parent_file_id,
            created=file.created,
            updated=file.updated,
            url=f"/api/v1/files/{file.id}/download",
        )
        return response
