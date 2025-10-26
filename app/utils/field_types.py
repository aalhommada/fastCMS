"""
Field type definitions and validators for dynamic collections.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FieldType(str, Enum):
    """Supported field types for collections."""

    TEXT = "text"
    NUMBER = "number"
    BOOL = "bool"
    EMAIL = "email"
    URL = "url"
    DATE = "date"
    DATETIME = "datetime"
    SELECT = "select"
    FILE = "file"
    RELATION = "relation"
    JSON = "json"
    EDITOR = "editor"


class FieldValidation(BaseModel):
    """Validation rules for a field."""

    required: bool = False
    unique: bool = False
    min: Optional[int | float] = None
    max: Optional[int | float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern
    values: Optional[List[Any]] = None  # Allowed values for select


class RelationOptions(BaseModel):
    """Options for relation fields."""

    collection_id: str = Field(..., description="Target collection ID")
    cascade_delete: bool = Field(default=False, description="Delete related records")
    display_fields: List[str] = Field(
        default_factory=lambda: ["id"],
        description="Fields to display in relation",
    )


class SelectOptions(BaseModel):
    """Options for select fields."""

    values: List[str] = Field(..., description="Available options")
    max_select: int = Field(default=1, description="Maximum selections (1 for single)")


class FileOptions(BaseModel):
    """Options for file fields."""

    max_size: int = Field(default=5242880, description="Max file size in bytes (5MB)")
    max_files: int = Field(default=1, description="Maximum number of files")
    mime_types: List[str] = Field(
        default_factory=lambda: ["image/jpeg", "image/png", "image/gif"],
        description="Allowed MIME types",
    )
    thumbs: List[str] = Field(
        default_factory=lambda: ["100x100", "500x500"],
        description="Thumbnail sizes",
    )


class FieldSchema(BaseModel):
    """Complete schema definition for a field."""

    name: str = Field(..., min_length=1, max_length=100, pattern="^[a-zA-Z][a-zA-Z0-9_]*$")
    type: FieldType
    validation: FieldValidation = Field(default_factory=FieldValidation)

    # Type-specific options
    relation: Optional[RelationOptions] = None
    select: Optional[SelectOptions] = None
    file: Optional[FileOptions] = None

    # Display options
    label: Optional[str] = None
    hint: Optional[str] = None
    hidden: bool = False
    system: bool = False  # System fields cannot be modified

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate field name is not a SQL reserved word."""
        sql_reserved = {
            "id", "created", "updated", "deleted",  # System fields
            "select", "from", "where", "insert", "update", "delete",  # SQL keywords
            "table", "index", "primary", "foreign", "key",
            "user", "group", "order", "limit", "offset",
        }

        if v.lower() in sql_reserved:
            raise ValueError(f"Field name '{v}' is reserved")

        return v

    @field_validator("relation", mode="after")
    @classmethod
    def validate_relation(cls, v: Optional[RelationOptions], info: Any) -> Optional[RelationOptions]:
        """Ensure relation options are provided for relation fields."""
        if info.data.get("type") == FieldType.RELATION and not v:
            raise ValueError("Relation fields require 'relation' options")
        return v

    @field_validator("select", mode="after")
    @classmethod
    def validate_select(cls, v: Optional[SelectOptions], info: Any) -> Optional[SelectOptions]:
        """Ensure select options are provided for select fields."""
        if info.data.get("type") == FieldType.SELECT and not v:
            raise ValueError("Select fields require 'select' options")
        return v


# SQL type mapping for field types
FIELD_TYPE_SQL_MAP: Dict[FieldType, str] = {
    FieldType.TEXT: "TEXT",
    FieldType.NUMBER: "REAL",
    FieldType.BOOL: "BOOLEAN",
    FieldType.EMAIL: "VARCHAR(255)",
    FieldType.URL: "VARCHAR(2048)",
    FieldType.DATE: "DATE",
    FieldType.DATETIME: "TIMESTAMP",
    FieldType.SELECT: "TEXT",
    FieldType.FILE: "TEXT",  # Stores file IDs as JSON array
    FieldType.RELATION: "VARCHAR(36)",  # UUID
    FieldType.JSON: "JSON",
    FieldType.EDITOR: "TEXT",
}


# Python type mapping for validation
FIELD_TYPE_PYTHON_MAP: Dict[FieldType, type] = {
    FieldType.TEXT: str,
    FieldType.NUMBER: (int, float),
    FieldType.BOOL: bool,
    FieldType.EMAIL: str,
    FieldType.URL: str,
    FieldType.DATE: str,  # ISO format string
    FieldType.DATETIME: str,  # ISO format string
    FieldType.SELECT: (str, list),
    FieldType.FILE: (str, list),
    FieldType.RELATION: str,
    FieldType.JSON: (dict, list),
    FieldType.EDITOR: str,
}
