"""
Business logic service for collection operations.
"""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.logging import get_logger
from app.db.models.collection import Collection
from app.db.models.dynamic import DynamicModelGenerator
from app.db.repositories.collection import CollectionRepository
from app.db.session import engine
from app.schemas.collection import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
)
from app.utils.field_types import FieldSchema

logger = get_logger(__name__)


class CollectionService:
    """Service for managing collections."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize service.

        Args:
            db: Async database session
        """
        self.db = db
        self.repo = CollectionRepository(db)

    async def create_collection(
        self,
        data: CollectionCreate,
    ) -> CollectionResponse:
        """
        Create a new collection.

        Args:
            data: Collection creation data

        Returns:
            Created collection response

        Raises:
            ConflictException: If collection with name already exists
            BadRequestException: If schema validation fails
        """
        # Check if collection already exists
        if await self.repo.exists(data.name):
            raise ConflictException(f"Collection '{data.name}' already exists")

        # Convert schema to dict for storage
        schema_dict = [field.model_dump() for field in data.schema]

        # Create collection record
        collection = Collection(
            name=data.name,
            type=data.type,
            schema={"fields": schema_dict},
            options=data.options,
            list_rule=data.list_rule,
            view_rule=data.view_rule,
            create_rule=data.create_rule,
            update_rule=data.update_rule,
            delete_rule=data.delete_rule,
            system=False,
        )

        # Save to database
        collection = await self.repo.create(collection)
        await self.db.commit()

        logger.info(f"Collection '{data.name}' created with ID: {collection.id}")

        # Create dynamic model and table
        try:
            model = DynamicModelGenerator.create_model(
                collection_name=data.name,
                fields=data.schema,
            )

            await DynamicModelGenerator.create_table(engine, model)

            logger.info(f"Database table '{data.name}' created successfully")

        except Exception as e:
            # Rollback collection creation if table creation fails
            await self.db.rollback()
            logger.error(f"Failed to create table for collection '{data.name}': {e}")
            raise BadRequestException(f"Failed to create collection table: {str(e)}")

        return self._to_response(collection)

    async def get_collection(self, collection_id: str) -> CollectionResponse:
        """
        Get collection by ID.

        Args:
            collection_id: Collection ID

        Returns:
            Collection response

        Raises:
            NotFoundException: If collection not found
        """
        collection = await self.repo.get_by_id(collection_id)

        if not collection:
            raise NotFoundException(f"Collection with ID '{collection_id}' not found")

        return self._to_response(collection)

    async def get_collection_by_name(self, name: str) -> CollectionResponse:
        """
        Get collection by name.

        Args:
            name: Collection name

        Returns:
            Collection response

        Raises:
            NotFoundException: If collection not found
        """
        collection = await self.repo.get_by_name(name)

        if not collection:
            raise NotFoundException(f"Collection '{name}' not found")

        return self._to_response(collection)

    async def list_collections(
        self,
        page: int = 1,
        per_page: int = 30,
        include_system: bool = False,
    ) -> tuple[List[CollectionResponse], int]:
        """
        List all collections with pagination.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            include_system: Include system collections

        Returns:
            Tuple of (collections, total_count)
        """
        skip = (page - 1) * per_page

        collections = await self.repo.get_all(
            skip=skip,
            limit=per_page,
            include_system=include_system,
        )

        total = await self.repo.count(include_system=include_system)

        return [self._to_response(c) for c in collections], total

    async def update_collection(
        self,
        collection_id: str,
        data: CollectionUpdate,
    ) -> CollectionResponse:
        """
        Update a collection.

        Args:
            collection_id: Collection ID
            data: Update data

        Returns:
            Updated collection response

        Raises:
            NotFoundException: If collection not found
            BadRequestException: If update fails
        """
        collection = await self.repo.get_by_id(collection_id)

        if not collection:
            raise NotFoundException(f"Collection with ID '{collection_id}' not found")

        if collection.system:
            raise BadRequestException("Cannot modify system collection")

        # Update fields
        if data.name is not None:
            # Check name uniqueness
            if data.name != collection.name and await self.repo.exists(data.name):
                raise ConflictException(f"Collection '{data.name}' already exists")
            collection.name = data.name

        if data.schema is not None:
            collection.schema = {"fields": [field.model_dump() for field in data.schema]}

        if data.options is not None:
            collection.options = data.options

        if data.list_rule is not None:
            collection.list_rule = data.list_rule

        if data.view_rule is not None:
            collection.view_rule = data.view_rule

        if data.create_rule is not None:
            collection.create_rule = data.create_rule

        if data.update_rule is not None:
            collection.update_rule = data.update_rule

        if data.delete_rule is not None:
            collection.delete_rule = data.delete_rule

        collection = await self.repo.update(collection)
        await self.db.commit()

        logger.info(f"Collection '{collection.name}' updated")

        # TODO: Handle schema changes (add/remove columns)
        # For now, we'll just clear the model cache
        DynamicModelGenerator.clear_cache(collection.name)

        return self._to_response(collection)

    async def delete_collection(self, collection_id: str) -> None:
        """
        Delete a collection.

        Args:
            collection_id: Collection ID

        Raises:
            NotFoundException: If collection not found
            BadRequestException: If trying to delete system collection
        """
        collection = await self.repo.get_by_id(collection_id)

        if not collection:
            raise NotFoundException(f"Collection with ID '{collection_id}' not found")

        if collection.system:
            raise BadRequestException("Cannot delete system collection")

        # Drop database table
        try:
            model = DynamicModelGenerator.get_model(collection.name)
            if model:
                await DynamicModelGenerator.drop_table(engine, model)
                logger.info(f"Database table '{collection.name}' dropped")

            # Clear cache
            DynamicModelGenerator.clear_cache(collection.name)

        except Exception as e:
            logger.warning(f"Failed to drop table '{collection.name}': {e}")
            # Continue with collection deletion even if table drop fails

        # Delete collection record
        await self.repo.delete(collection)
        await self.db.commit()

        logger.info(f"Collection '{collection.name}' deleted")

    def _to_response(self, collection: Collection) -> CollectionResponse:
        """
        Convert collection model to response schema.

        Args:
            collection: Collection model

        Returns:
            Collection response schema
        """
        # Parse schema from JSON
        fields = [
            FieldSchema(**field_data)
            for field_data in collection.schema.get("fields", [])
        ]

        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            type=collection.type,
            schema=fields,
            options=collection.options,
            list_rule=collection.list_rule,
            view_rule=collection.view_rule,
            create_rule=collection.create_rule,
            update_rule=collection.update_rule,
            delete_rule=collection.delete_rule,
            system=collection.system,
            created=collection.created,
            updated=collection.updated,
        )
