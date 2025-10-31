"""Repository for file operations."""
from typing import List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.file import File


class FileRepository:
    """Repository for CRUD operations on files."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, file_data: dict) -> File:
        """Create a new file record."""
        file = File(**file_data)
        self.db.add(file)
        await self.db.flush()
        await self.db.refresh(file)
        return file

    async def get_by_id(self, file_id: str) -> Optional[File]:
        """Get a file by ID."""
        result = await self.db.execute(
            select(File).where(File.id == file_id, File.deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        collection_name: Optional[str] = None,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[File]:
        """Get all files with optional filtering."""
        query = select(File).where(File.deleted == False)

        if collection_name:
            query = query.where(File.collection_name == collection_name)

        if record_id:
            query = query.where(File.record_id == record_id)

        if user_id:
            query = query.where(File.user_id == user_id)

        query = query.order_by(desc(File.created)).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        collection_name: Optional[str] = None,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> int:
        """Count files with optional filtering."""
        query = select(func.count(File.id)).where(File.deleted == False)

        if collection_name:
            query = query.where(File.collection_name == collection_name)

        if record_id:
            query = query.where(File.record_id == record_id)

        if user_id:
            query = query.where(File.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def soft_delete(self, file_id: str) -> bool:
        """Soft delete a file."""
        file = await self.get_by_id(file_id)
        if not file:
            return False

        file.deleted = True
        await self.db.flush()
        return True

    async def get_thumbnails(self, parent_file_id: str) -> List[File]:
        """Get all thumbnails for a file."""
        result = await self.db.execute(
            select(File).where(
                File.parent_file_id == parent_file_id,
                File.is_thumbnail == True,
                File.deleted == False,
            )
        )
        return list(result.scalars().all())
