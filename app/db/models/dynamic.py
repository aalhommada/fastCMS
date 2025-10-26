"""
Dynamic model generator for creating SQLAlchemy models at runtime.
"""

from datetime import datetime
from typing import Any, Dict, Type

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON as SQLJSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.base import BaseModel, generate_uuid, utcnow
from app.utils.field_types import FieldSchema, FieldType


class DynamicModelGenerator:
    """Generator for creating SQLAlchemy models dynamically."""

    # Cache for generated models
    _model_cache: Dict[str, Type[BaseModel]] = {}

    @classmethod
    def _get_column_for_field(cls, field: FieldSchema) -> Column:
        """
        Get SQLAlchemy column definition for a field.

        Args:
            field: Field schema

        Returns:
            SQLAlchemy Column instance
        """
        # Base column kwargs
        kwargs: Dict[str, Any] = {
            "nullable": not field.validation.required,
        }

        # Add unique constraint
        if field.validation.unique:
            kwargs["unique"] = True
            kwargs["index"] = True
        elif field.type == FieldType.RELATION:
            # Index relation fields for performance
            kwargs["index"] = True

        # Map field type to SQLAlchemy type
        if field.type == FieldType.TEXT or field.type == FieldType.EDITOR:
            if field.validation.max_length and field.validation.max_length <= 255:
                column_type = String(field.validation.max_length)
            else:
                column_type = Text
        elif field.type == FieldType.NUMBER:
            column_type = Float
        elif field.type == FieldType.BOOL:
            column_type = Boolean
        elif field.type == FieldType.EMAIL:
            column_type = String(255)
        elif field.type == FieldType.URL:
            column_type = String(2048)
        elif field.type == FieldType.DATE:
            column_type = Date
        elif field.type == FieldType.DATETIME:
            column_type = DateTime(timezone=True)
        elif field.type == FieldType.RELATION:
            # Relation is a foreign key to another collection
            column_type = String(36)  # UUID
            if field.relation:
                # Note: We'll handle the actual FK constraint in a separate step
                # because we need to know the target table name
                pass
        elif field.type == FieldType.SELECT:
            # Select stores value(s) as text or JSON for multi-select
            column_type = Text if field.select and field.select.max_select == 1 else SQLJSON
        elif field.type == FieldType.FILE:
            # File stores file IDs as JSON array
            column_type = SQLJSON
        elif field.type == FieldType.JSON:
            column_type = SQLJSON
        else:
            column_type = Text

        return Column(field.name, column_type, **kwargs)

    @classmethod
    def create_model(
        cls,
        collection_name: str,
        fields: list[FieldSchema],
        clear_cache: bool = False,
    ) -> Type[BaseModel]:
        """
        Create a dynamic SQLAlchemy model for a collection.

        Args:
            collection_name: Name of the collection (table name)
            fields: List of field schemas
            clear_cache: Force regeneration by clearing cache

        Returns:
            Dynamically created model class
        """
        # Check cache
        if not clear_cache and collection_name in cls._model_cache:
            return cls._model_cache[collection_name]

        # Build column definitions
        columns: Dict[str, Any] = {
            "__tablename__": collection_name,
            "__table_args__": {"extend_existing": True},
        }

        # Add custom fields
        for field in fields:
            columns[field.name] = cls._get_column_for_field(field)

        # Create the model class dynamically
        model_name = f"{collection_name.capitalize()}Model"
        model_class = type(
            model_name,
            (BaseModel,),
            columns,
        )

        # Cache the model
        cls._model_cache[collection_name] = model_class

        return model_class

    @classmethod
    def get_model(cls, collection_name: str) -> Type[BaseModel] | None:
        """
        Get a cached model by collection name.

        Args:
            collection_name: Name of the collection

        Returns:
            Model class or None if not cached
        """
        return cls._model_cache.get(collection_name)

    @classmethod
    def clear_cache(cls, collection_name: str | None = None) -> None:
        """
        Clear model cache.

        Args:
            collection_name: Specific collection to clear, or None for all
        """
        if collection_name:
            cls._model_cache.pop(collection_name, None)
        else:
            cls._model_cache.clear()

    @classmethod
    async def create_table(
        cls,
        engine: Any,
        model: Type[BaseModel],
    ) -> None:
        """
        Create database table for a model.

        Args:
            engine: SQLAlchemy async engine
            model: Model class to create table for
        """
        async with engine.begin() as conn:
            await conn.run_sync(model.metadata.create_all)

    @classmethod
    async def drop_table(
        cls,
        engine: Any,
        model: Type[BaseModel],
    ) -> None:
        """
        Drop database table for a model.

        Args:
            engine: SQLAlchemy async engine
            model: Model class to drop table for
        """
        async with engine.begin() as conn:
            await conn.run_sync(model.metadata.drop_all)
