"""File schemas for upload and response."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class FileUpload(BaseModel):
    """Schema for file upload metadata."""

    collection_name: Optional[str] = None
    record_id: Optional[str] = None
    field_name: Optional[str] = None


class FileResponse(BaseModel):
    """Schema for file response."""

    id: str
    filename: str
    original_filename: str
    mime_type: str
    size: int
    storage_path: str
    storage_type: str
    collection_name: Optional[str] = None
    record_id: Optional[str] = None
    field_name: Optional[str] = None
    user_id: Optional[str] = None
    is_thumbnail: bool
    parent_file_id: Optional[str] = None
    created: datetime
    updated: datetime
    url: Optional[str] = None  # Computed field for download URL

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Schema for paginated file list."""

    items: List[FileResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
