"""Service for file upload, download, and management."""
import uuid
from app.utils.timeutils import utcnow
import math
from pathlib import Path
from typing import Optional, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image

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

        # Generate thumbnails for images
        if mime_type.startswith("image/"):
            await self._generate_thumbnails(file, full_path)

        return self._to_response(file)

    async def get_file(self, file_id: str) -> FileResponse:
        """Get file metadata by ID."""
        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        return self._to_response(file)

    async def get_file_content(
        self,
        file_id: str,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> tuple[Path, str, str]:
        """
        Get file content for download.

        For protected files, either a valid file token or an authenticated user_id is required.
        """
        from app.core.security import verify_file_token
        from app.core.exceptions import ForbiddenException

        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        if file.protected:
            # Allow if a valid short-lived file token is provided
            if token:
                authorized_user = verify_file_token(token, file_id)
                if not authorized_user:
                    raise ForbiddenException("Invalid or expired file token")
            elif user_id:
                pass  # Authenticated users may access (rule-based enforcement can be added later)
            else:
                raise ForbiddenException("This file is protected. Provide a valid file token.")

        file_path = self.storage_path / file.storage_path
        if not file_path.exists():
            raise NotFoundException("File content not found on disk")

        return file_path, file.original_filename, file.mime_type

    async def create_file_token(self, file_id: str, user_id: str) -> str:
        """Generate a short-lived access token for a protected file."""
        from app.core.security import generate_file_token

        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        return generate_file_token(user_id, file_id)

    async def set_file_protected(self, file_id: str, protected: bool) -> None:
        """Mark a file as protected or unprotected."""
        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        file.protected = protected
        await self.repo.update(file)

    async def get_file_thumb(self, file_id: str, thumb_spec: str) -> tuple[Path, str]:
        """
        Return path to a on-demand thumbnail, generating and caching it if needed.

        Args:
            file_id: File ID
            thumb_spec: Spec string, e.g. '300x200', '300x200f', '0x150'

        Returns:
            (thumb_path, mime_type) — always JPEG for on-demand thumbs
        """
        from app.services.image_processor import ImageProcessor

        file = await self.repo.get_by_id(file_id)
        if not file:
            raise NotFoundException(f"File '{file_id}' not found")

        if not ImageProcessor.is_image(file.mime_type):
            raise BadRequestException("Thumbnail generation is only supported for image files")

        # Parse spec — raises ValueError on bad input
        try:
            width, height, mode = ImageProcessor.parse_thumb_spec(thumb_spec)
        except ValueError as e:
            raise BadRequestException(str(e))

        # Cache location: {storage_path}/thumbs/{spec}/{original_stem}.jpg
        safe_spec = thumb_spec.lower().replace(" ", "")
        original_path = self.storage_path / file.storage_path
        stem = Path(file.original_filename).stem
        cache_dir = self.storage_path / "thumbs" / safe_spec
        cache_path = cache_dir / f"{stem}_{file.id}.jpg"

        if cache_path.exists():
            return cache_path, "image/jpeg"

        # Read original
        if not original_path.exists():
            raise NotFoundException("File content not found on disk")

        image_data = original_path.read_bytes()

        # Generate
        thumb_bytes = await ImageProcessor.generate_thumb_on_demand(
            image_data=image_data,
            width=width,
            height=height,
            mode=mode,
        )

        # Save to cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(thumb_bytes)

        return cache_path, "image/jpeg"

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

        now = utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")

        return f"{year}/{month}/{day}/{filename}"

    async def _generate_thumbnails(self, file, original_path: Path):
        """Generate thumbnails for an image file."""
        thumbnail_sizes = [
            ("thumb_100", 100),
            ("thumb_300", 300),
            ("thumb_500", 500),
        ]

        try:
            with Image.open(original_path) as original_img:
                # Convert RGBA to RGB if necessary
                if original_img.mode == "RGBA":
                    background = Image.new("RGB", original_img.size, (255, 255, 255))
                    background.paste(original_img, mask=original_img.split()[3])
                    original_img = background
                elif original_img.mode != "RGB":
                    original_img = original_img.convert("RGB")

                for size_name, max_size in thumbnail_sizes:
                    # Create a copy for each thumbnail size
                    img = original_img.copy()

                    # Calculate new dimensions maintaining aspect ratio
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                    # Generate thumbnail filename
                    thumb_filename = f"{file.filename.rsplit('.', 1)[0]}_{size_name}.jpg"
                    thumb_relative_path = self._get_storage_path(thumb_filename)
                    thumb_full_path = self.storage_path / thumb_relative_path

                    # Ensure parent directory exists
                    thumb_full_path.parent.mkdir(parents=True, exist_ok=True)

                    # Save thumbnail
                    img.save(thumb_full_path, "JPEG", quality=85, optimize=True)

                    # Get file size
                    thumb_size = thumb_full_path.stat().st_size

                    # Create thumbnail database record
                    thumb_data = {
                        "filename": thumb_filename,
                        "original_filename": f"{size_name}_{file.original_filename}",
                        "mime_type": "image/jpeg",
                        "size": thumb_size,
                        "storage_path": str(thumb_relative_path),
                        "storage_type": settings.STORAGE_TYPE,
                        "user_id": file.user_id,
                        "is_thumbnail": True,
                        "parent_file_id": file.id,
                        "collection_name": file.collection_name,
                        "record_id": file.record_id,
                        "field_name": file.field_name,
                    }

                    await self.repo.create(thumb_data)

                await self.db.commit()

        except Exception as e:
            # Log error but don't fail the upload
            from app.core.logging import get_logger

            logger = get_logger(__name__)
            logger.error(f"Failed to generate thumbnails: {str(e)}")

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
