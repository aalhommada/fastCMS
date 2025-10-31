"""File model for storing uploaded file metadata."""
from typing import Optional
from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class File(BaseModel):
    """File model storing metadata for uploaded files."""

    __tablename__ = "files"

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)  # Size in bytes

    # Storage information
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(20), nullable=False, default="local")

    # Optional metadata
    collection_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # User who uploaded the file
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Thumbnail flag (for images)
    is_thumbnail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parent_file_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Soft delete
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
