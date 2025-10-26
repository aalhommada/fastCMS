"""
Repository for Collection database operations.
"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.collection import Collection


class CollectionRepository:
    """Repository for collection CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            db: Async database session
        """
        self.db = db

    async def create(self, collection: Collection) -> Collection:
        """
        Create a new collection.

        Args:
            collection: Collection instance to create

        Returns:
            Created collection
        """
        self.db.add(collection)
        await self.db.flush()
        await self.db.refresh(collection)
        return collection

    async def get_by_id(self, collection_id: str) -> Optional[Collection]:
        """
        Get collection by ID.

        Args:
            collection_id: Collection ID

        Returns:
            Collection or None if not found
        """
        result = await self.db.execute(
            select(Collection).where(Collection.id == collection_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Collection]:
        """
        Get collection by name.

        Args:
            name: Collection name

        Returns:
            Collection or None if not found
        """
        result = await self.db.execute(
            select(Collection).where(Collection.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        include_system: bool = True,
    ) -> List[Collection]:
        """
        Get all collections with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_system: Include system collections

        Returns:
            List of collections
        """
        query = select(Collection)

        if not include_system:
            query = query.where(Collection.system == False)

        query = query.offset(skip).limit(limit).order_by(Collection.created.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(self, include_system: bool = True) -> int:
        """
        Count total collections.

        Args:
            include_system: Include system collections

        Returns:
            Total count
        """
        query = select(func.count(Collection.id))

        if not include_system:
            query = query.where(Collection.system == False)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def update(self, collection: Collection) -> Collection:
        """
        Update a collection.

        Args:
            collection: Collection instance with updated data

        Returns:
            Updated collection
        """
        await self.db.flush()
        await self.db.refresh(collection)
        return collection

    async def delete(self, collection: Collection) -> None:
        """
        Delete a collection.

        Args:
            collection: Collection to delete
        """
        await self.db.delete(collection)
        await self.db.flush()

    async def exists(self, name: str) -> bool:
        """
        Check if collection exists by name.

        Args:
            name: Collection name

        Returns:
            True if exists, False otherwise
        """
        result = await self.db.execute(
            select(func.count(Collection.id)).where(Collection.name == name)
        )
        count = result.scalar_one()
        return count > 0
