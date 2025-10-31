"""Repository for dynamic record operations."""
from typing import Any, Dict, List, Optional, Type
from sqlalchemy import select, func, and_, or_, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.dynamic import DynamicModelGenerator
from app.db.models.base import BaseModel
from app.schemas.record import RecordFilter


class RecordRepository:
    """Repository for CRUD operations on dynamic collection records."""

    def __init__(self, db: AsyncSession, collection_name: str):
        self.db = db
        self.collection_name = collection_name
        self.model: Optional[Type[BaseModel]] = None

    async def _get_model(self) -> Type[BaseModel]:
        """Get or cache the dynamic model for this collection."""
        if self.model is None:
            self.model = await DynamicModelGenerator.get_model(self.collection_name)
            if self.model is None:
                raise ValueError(f"Collection '{self.collection_name}' does not exist")
        return self.model

    async def create(self, data: Dict[str, Any]) -> BaseModel:
        """Create a new record."""
        model = await self._get_model()
        record = model(**data)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_by_id(self, record_id: str) -> Optional[BaseModel]:
        """Get a record by ID."""
        model = await self._get_model()
        result = await self.db.execute(
            select(model).where(model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[List[RecordFilter]] = None,
        sort_field: Optional[str] = None,
        sort_order: str = "asc",
    ) -> List[BaseModel]:
        """Get all records with optional filtering and sorting."""
        model = await self._get_model()
        query = select(model)

        # Apply filters
        if filters:
            query = self._apply_filters(query, model, filters)

        # Apply sorting
        if sort_field and hasattr(model, sort_field):
            sort_col = getattr(model, sort_field)
            query = query.order_by(desc(sort_col) if sort_order == "desc" else asc(sort_col))
        else:
            # Default sort by created desc
            query = query.order_by(desc(model.created))

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars.all())

    async def count(self, filters: Optional[List[RecordFilter]] = None) -> int:
        """Count records with optional filtering."""
        model = await self._get_model()
        query = select(func.count(model.id))

        # Apply filters
        if filters:
            query = self._apply_filters(query, model, filters)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def update(self, record_id: str, data: Dict[str, Any]) -> Optional[BaseModel]:
        """Update a record."""
        record = await self.get_by_id(record_id)
        if not record:
            return None

        for key, value in data.items():
            if hasattr(record, key):
                setattr(record, key, value)

        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def delete(self, record_id: str) -> bool:
        """Delete a record."""
        record = await self.get_by_id(record_id)
        if not record:
            return False

        await self.db.delete(record)
        await self.db.flush()
        return True

    def _apply_filters(self, query, model: Type[BaseModel], filters: List[RecordFilter]):
        """Apply filters to query."""
        conditions = []

        for f in filters:
            if not hasattr(model, f.field):
                continue

            field = getattr(model, f.field)

            if f.operator == "eq":
                conditions.append(field == f.value)
            elif f.operator == "ne":
                conditions.append(field != f.value)
            elif f.operator == "gt":
                conditions.append(field > f.value)
            elif f.operator == "lt":
                conditions.append(field < f.value)
            elif f.operator == "gte":
                conditions.append(field >= f.value)
            elif f.operator == "lte":
                conditions.append(field <= f.value)
            elif f.operator == "like":
                conditions.append(field.like(f"%{f.value}%"))
            elif f.operator == "in":
                if isinstance(f.value, list):
                    conditions.append(field.in_(f.value))

        if conditions:
            query = query.where(and_(*conditions))

        return query
