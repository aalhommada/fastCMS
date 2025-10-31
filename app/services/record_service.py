"""Service for record CRUD operations with validation."""
import math
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.repositories.record import RecordRepository
from app.db.repositories.collection import CollectionRepository
from app.schemas.record import (
    RecordCreate,
    RecordUpdate,
    RecordResponse,
    RecordListResponse,
    RecordFilter,
)
from app.utils.field_types import FieldSchema, FieldType
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    BadRequestException,
)


class RecordService:
    """Service for managing records in dynamic collections."""

    def __init__(self, db: AsyncSession, collection_name: str):
        self.db = db
        self.collection_name = collection_name
        self.repo = RecordRepository(db, collection_name)
        self.collection_repo = CollectionRepository(db)

    async def create_record(self, data: RecordCreate) -> RecordResponse:
        """Create a new record with validation."""
        # Get collection schema
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if not collection:
            raise NotFoundException(f"Collection '{self.collection_name}' not found")

        # Extract fields from schema
        fields = collection.schema.get("fields", [])
        field_schemas = [FieldSchema(**field) for field in fields]

        # Validate data against schema
        validated_data = self._validate_fields(data.data, field_schemas, is_create=True)

        # Create record
        record = await self.repo.create(validated_data)
        await self.db.commit()

        return self._to_response(record)

    async def get_record(self, record_id: str) -> RecordResponse:
        """Get a record by ID."""
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise NotFoundException(f"Record '{record_id}' not found")

        return self._to_response(record)

    async def list_records(
        self,
        page: int = 1,
        per_page: int = 20,
        filters: Optional[List[RecordFilter]] = None,
        sort: Optional[str] = None,
        order: str = "asc",
    ) -> RecordListResponse:
        """List records with pagination, filtering, and sorting."""
        # Validate collection exists
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if not collection:
            raise NotFoundException(f"Collection '{self.collection_name}' not found")

        skip = (page - 1) * per_page

        # Get records and total count
        records = await self.repo.get_all(
            skip=skip,
            limit=per_page,
            filters=filters,
            sort_field=sort,
            sort_order=order,
        )
        total = await self.repo.count(filters=filters)

        items = [self._to_response(record) for record in records]
        total_pages = math.ceil(total / per_page) if total > 0 else 0

        return RecordListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def update_record(self, record_id: str, data: RecordUpdate) -> RecordResponse:
        """Update a record with validation."""
        # Check if record exists
        existing = await self.repo.get_by_id(record_id)
        if not existing:
            raise NotFoundException(f"Record '{record_id}' not found")

        # Get collection schema
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if not collection:
            raise NotFoundException(f"Collection '{self.collection_name}' not found")

        # Extract fields from schema
        fields = collection.schema.get("fields", [])
        field_schemas = [FieldSchema(**field) for field in fields]

        # Validate data against schema
        validated_data = self._validate_fields(data.data, field_schemas, is_create=False)

        # Update record
        updated_record = await self.repo.update(record_id, validated_data)
        await self.db.commit()

        return self._to_response(updated_record)

    async def delete_record(self, record_id: str) -> None:
        """Delete a record."""
        success = await self.repo.delete(record_id)
        if not success:
            raise NotFoundException(f"Record '{record_id}' not found")

        await self.db.commit()

    def _validate_fields(
        self, data: Dict[str, Any], field_schemas: List[FieldSchema], is_create: bool
    ) -> Dict[str, Any]:
        """Validate record data against collection schema."""
        validated = {}
        errors = {}

        # Check required fields (only on create)
        if is_create:
            for field_schema in field_schemas:
                if field_schema.validation.required and field_schema.name not in data:
                    errors[field_schema.name] = "This field is required"

        # Validate provided fields
        for field_name, value in data.items():
            # Find field schema
            field_schema = next(
                (f for f in field_schemas if f.name == field_name), None
            )

            if not field_schema:
                # Ignore unknown fields
                continue

            # Skip validation if value is None and field is not required
            if value is None and not field_schema.validation.required:
                validated[field_name] = None
                continue

            # Validate field
            try:
                validated_value = self._validate_field(value, field_schema)
                validated[field_name] = validated_value
            except ValueError as e:
                errors[field_name] = str(e)

        if errors:
            raise ValidationException("Validation failed", details={"fields": errors})

        return validated

    def _validate_field(self, value: Any, field_schema: FieldSchema) -> Any:
        """Validate a single field value."""
        validation = field_schema.validation

        # Type-specific validation
        if field_schema.type == FieldType.TEXT or field_schema.type == FieldType.EDITOR:
            if not isinstance(value, str):
                raise ValueError("Must be a string")

            if validation.min_length and len(value) < validation.min_length:
                raise ValueError(f"Minimum length is {validation.min_length}")

            if validation.max_length and len(value) > validation.max_length:
                raise ValueError(f"Maximum length is {validation.max_length}")

            if validation.pattern:
                import re
                if not re.match(validation.pattern, value):
                    raise ValueError("Does not match required pattern")

        elif field_schema.type == FieldType.NUMBER:
            if not isinstance(value, (int, float)):
                raise ValueError("Must be a number")

            if validation.min is not None and value < validation.min:
                raise ValueError(f"Minimum value is {validation.min}")

            if validation.max is not None and value > validation.max:
                raise ValueError(f"Maximum value is {validation.max}")

        elif field_schema.type == FieldType.BOOL:
            if not isinstance(value, bool):
                raise ValueError("Must be a boolean")

        elif field_schema.type == FieldType.EMAIL:
            if not isinstance(value, str):
                raise ValueError("Must be a string")
            # Basic email validation
            if "@" not in value or "." not in value:
                raise ValueError("Invalid email format")

        elif field_schema.type == FieldType.URL:
            if not isinstance(value, str):
                raise ValueError("Must be a string")
            if not value.startswith(("http://", "https://")):
                raise ValueError("Invalid URL format")

        elif field_schema.type == FieldType.DATE:
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    raise ValueError("Invalid date format")
            elif not isinstance(value, datetime):
                raise ValueError("Must be a date string or datetime")

        elif field_schema.type == FieldType.SELECT:
            if validation.values and value not in validation.values:
                raise ValueError(f"Must be one of: {', '.join(validation.values)}")

        elif field_schema.type == FieldType.RELATION:
            if not isinstance(value, str):
                raise ValueError("Must be a string (record ID)")

        elif field_schema.type == FieldType.FILE:
            if not isinstance(value, list):
                raise ValueError("Must be an array of file IDs")

        elif field_schema.type == FieldType.JSON:
            # JSON accepts any structure
            pass

        return value

    def _to_response(self, record) -> RecordResponse:
        """Convert record model to response schema."""
        # Extract data fields (exclude system fields)
        data = {}
        for key in dir(record):
            if not key.startswith("_") and key not in ["id", "created", "updated", "metadata", "registry"]:
                value = getattr(record, key)
                # Skip SQLAlchemy internal attributes
                if not callable(value) and not key.startswith("_sa_"):
                    data[key] = value

        return RecordResponse(
            id=record.id,
            data=data,
            created=record.created,
            updated=record.updated,
        )
