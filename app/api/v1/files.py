"""API endpoints for file upload and management."""
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.file_service import FileService
from app.schemas.file import FileResponse as FileResponseSchema, FileListResponse, FileUpload
from app.core.dependencies import require_auth, get_optional_user_id


router = APIRouter()


@router.post(
    "/files",
    response_model=FileResponseSchema,
    status_code=201,
    summary="Upload a file",
)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    collection_name: Optional[str] = Form(None, description="Collection name"),
    record_id: Optional[str] = Form(None, description="Record ID"),
    field_name: Optional[str] = Form(None, description="Field name"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
):
    """Upload a file with optional metadata linking to a collection record."""
    service = FileService(db)

    metadata = FileUpload(
        collection_name=collection_name,
        record_id=record_id,
        field_name=field_name,
    )

    return await service.upload_file(
        file_content=file.file,
        filename=file.filename,
        mime_type=file.content_type,
        size=file.size,
        user_id=user_id,
        metadata=metadata,
    )


@router.get(
    "/files",
    response_model=FileListResponse,
    summary="List files",
)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    collection_name: Optional[str] = Query(None, description="Filter by collection"),
    record_id: Optional[str] = Query(None, description="Filter by record ID"),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """List all files with optional filtering."""
    service = FileService(db)
    return await service.list_files(
        page=page,
        per_page=per_page,
        collection_name=collection_name,
        record_id=record_id,
        user_id=user_id if user_id else None,
    )


@router.get(
    "/files/{file_id}",
    response_model=FileResponseSchema,
    summary="Get file metadata",
)
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Get file metadata by ID."""
    service = FileService(db)
    return await service.get_file(file_id)


@router.get(
    "/files/{file_id}/download",
    response_class=FileResponse,
    summary="Download file",
)
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Download file content."""
    service = FileService(db)
    file_path, original_filename, mime_type = await service.get_file_content(file_id)

    return FileResponse(
        path=file_path,
        filename=original_filename,
        media_type=mime_type,
    )


@router.delete(
    "/files/{file_id}",
    status_code=204,
    summary="Delete file",
)
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
):
    """Delete a file."""
    service = FileService(db)
    await service.delete_file(file_id)
    return None
