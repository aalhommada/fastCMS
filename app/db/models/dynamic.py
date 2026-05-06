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
        elif field.type == FieldType.AUTODATE:
            column_type = DateTime(timezone=True)
            # Always nullable since we manage it in service layer
            kwargs["nullable"] = True
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
        # Also drop the Table from SQLAlchemy's MetaData. Without this, the
        # next create_model call uses extend_existing=True against the stale
        # Table — which only ADDS columns, so dropped columns linger and
        # subsequent INSERTs fail referencing columns that no longer exist
        # on disk. Only remove tables we know we created (tracked via the
        # cache) so we never touch system tables like users/settings.
        from app.db.base import metadata as _md

        names_to_drop = (
            [collection_name] if collection_name else list(cls._model_cache.keys())
        )

        if collection_name:
            cls._model_cache.pop(collection_name, None)
        else:
            cls._model_cache.clear()

        for name in names_to_drop:
            tbl = _md.tables.get(name)
            if tbl is not None:
                _md.remove(tbl)

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
            # Use Base.metadata to create only this specific table
            def create_tables(connection):
                # Create only the tables for this model
                model.__table__.create(connection, checkfirst=True)

            await conn.run_sync(create_tables)

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

    @classmethod
    async def add_column(
        cls,
        engine: Any,
        table_name: str,
        field: FieldSchema,
    ) -> None:
        """
        Add a column to an existing table.

        Args:
            engine: SQLAlchemy async engine
            table_name: Name of the table
            field: Field schema for the new column
        """
        from sqlalchemy import text

        # Get column definition
        column = cls._get_column_for_field(field)
        column_type = cls._get_sql_type_string(field)

        # Build ALTER TABLE statement
        nullable = "NULL" if not field.validation.required else "NOT NULL"
        default_clause = cls._get_default_clause(field)

        sql = f"ALTER TABLE {table_name} ADD COLUMN {field.name} {column_type} {nullable} {default_clause}"

        async with engine.begin() as conn:
            await conn.execute(text(sql.strip()))

    @classmethod
    async def drop_column(
        cls,
        engine: Any,
        table_name: str,
        column_name: str,
    ) -> None:
        """
        Drop a column from an existing table.

        Note: SQLite doesn't support DROP COLUMN directly in older versions.
        For SQLite < 3.35.0, this uses a table rebuild approach.

        Args:
            engine: SQLAlchemy async engine
            table_name: Name of the table
            column_name: Name of the column to drop
        """
        from sqlalchemy import text

        # For modern SQLite (3.35.0+) and PostgreSQL/MySQL
        sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"

        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception as e:
            # Fallback for older SQLite versions - more complex approach needed
            # For now, log and skip the column drop
            from app.core.logging import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Could not drop column {column_name} from {table_name}: {e}")

    @classmethod
    async def rename_column(
        cls,
        engine: Any,
        table_name: str,
        old_name: str,
        new_name: str,
    ) -> None:
        """
        Rename a column in an existing table.

        Args:
            engine: SQLAlchemy async engine
            table_name: Name of the table
            old_name: Current column name
            new_name: New column name
        """
        from sqlalchemy import text

        # Works for SQLite 3.25.0+, PostgreSQL, MySQL
        sql = f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}"

        async with engine.begin() as conn:
            await conn.execute(text(sql))

    @classmethod
    async def migrate_schema(
        cls,
        engine: Any,
        table_name: str,
        old_fields: list[FieldSchema],
        new_fields: list[FieldSchema],
    ) -> dict:
        """
        Migrate table schema by comparing old and new field definitions.

        Args:
            engine: SQLAlchemy async engine
            table_name: Name of the table
            old_fields: Previous field schemas
            new_fields: New field schemas

        Returns:
            Dictionary with migration results:
            - added: List of added field names
            - removed: List of removed field names
            - renamed: List of (old_name, new_name) tuples
        """
        old_field_map = {f.name: f for f in old_fields}
        new_field_map = {f.name: f for f in new_fields}

        old_names = set(old_field_map.keys())
        new_names = set(new_field_map.keys())

        # Fields to add (in new but not in old)
        to_add = new_names - old_names
        # Fields to remove (in old but not in new)
        to_remove = old_names - new_names

        added = []
        removed = []

        # Add new columns
        for name in to_add:
            try:
                await cls.add_column(engine, table_name, new_field_map[name])
                added.append(name)
            except Exception as e:
                from app.core.logging import get_logger
                logger = get_logger(__name__)
                logger.error(f"Failed to add column {name}: {e}")

        # Remove old columns
        for name in to_remove:
            try:
                await cls.drop_column(engine, table_name, name)
                removed.append(name)
            except Exception as e:
                from app.core.logging import get_logger
                logger = get_logger(__name__)
                logger.error(f"Failed to drop column {name}: {e}")

        # Clear the model cache to regenerate with new schema
        cls.clear_cache(table_name)

        return {
            "added": added,
            "removed": removed,
            "renamed": [],  # Rename detection would need additional logic
        }

    @classmethod
    def _get_sql_type_string(cls, field: FieldSchema) -> str:
        """Get SQL type string for a field."""
        if field.type == FieldType.TEXT or field.type == FieldType.EDITOR:
            if field.validation.max_length and field.validation.max_length <= 255:
                return f"VARCHAR({field.validation.max_length})"
            return "TEXT"
        elif field.type == FieldType.NUMBER:
            return "REAL"
        elif field.type == FieldType.BOOL:
            return "BOOLEAN"
        elif field.type == FieldType.EMAIL:
            return "VARCHAR(255)"
        elif field.type == FieldType.URL:
            return "VARCHAR(2048)"
        elif field.type == FieldType.DATE:
            return "DATE"
        elif field.type == FieldType.DATETIME:
            return "TIMESTAMP"
        elif field.type == FieldType.RELATION:
            return "VARCHAR(36)"
        elif field.type == FieldType.GEOPOINT:
            return "JSON"
        elif field.type in (FieldType.SELECT, FieldType.FILE, FieldType.JSON):
            return "JSON"
        return "TEXT"

    @classmethod
    def _get_default_clause(cls, field: FieldSchema) -> str:
        """Get default clause for a field."""
        if field.type == FieldType.BOOL:
            return "DEFAULT 0"
        elif field.type == FieldType.NUMBER:
            return "DEFAULT 0"
        elif field.type in (FieldType.SELECT, FieldType.FILE, FieldType.JSON, FieldType.GEOPOINT):
            return "DEFAULT NULL"
        return "DEFAULT ''"
