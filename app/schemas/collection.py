"""
Pydantic schemas for collection endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.field_types import FieldSchema


class CollectionBase(BaseModel):
    """Base collection schema with common fields."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z][a-zA-Z0-9_]*$",
        description="Collection name (must be unique)",
    )

    type: Literal["base", "auth", "view"] = Field(
        default="base",
        description="Collection type",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate collection name."""
        reserved = {"collections", "users", "system"}
        if v.lower() in reserved:
            raise ValueError(f"Collection name '{v}' is reserved")
        return v


class CollectionCreate(CollectionBase):
    """Schema for creating a collection."""

    schema: List[FieldSchema] = Field(
        ...,
        min_length=0,
        description="List of field schemas",
    )

    options: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Collection options. For auth collections, supports: "
            "identity_field (str, default 'email') — field used as login identity."
        ),
    )

    # Access control rules
    list_rule: Optional[str] = Field(
        default=None,
        description="Rule for listing records",
    )
    view_rule: Optional[str] = Field(
        default=None,
        description="Rule for viewing a single record",
    )
    create_rule: Optional[str] = Field(
        default=None,
        description="Rule for creating records",
    )
    update_rule: Optional[str] = Field(
        default=None,
        description="Rule for updating records",
    )
    delete_rule: Optional[str] = Field(
        default=None,
        description="Rule for deleting records",
    )
    manage_rule: Optional[str] = Field(
        default=None,
        description="Rule for managing other users' records in auth collections",
    )

    # View query (required for view collections)
    view_query: Optional[str] = Field(
        default=None,
        description="SQL SELECT query for view collections",
    )

    @field_validator("schema")
    @classmethod
    def validate_schema(cls, v: List[FieldSchema]) -> List[FieldSchema]:
        """Validate schema has unique field names."""
        names = [field.name for field in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate field names in schema")
        return v

    @field_validator("view_query")
    @classmethod
    def validate_view_query(cls, v: Optional[str], values: dict) -> Optional[str]:
        """Validate view_query is provided for view collections."""
        collection_type = values.data.get("type")
        if collection_type == "view" and not v:
            raise ValueError("view_query is required for view collections")
        if collection_type != "view" and v:
            raise ValueError("view_query is only allowed for view collections")
        return v


class CollectionUpdate(BaseModel):
    """Schema for updating a collection."""

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z][a-zA-Z0-9_]*$",
    )

    schema: Optional[List[FieldSchema]] = None
    options: Optional[Dict[str, Any]] = None

    list_rule: Optional[str] = None
    view_rule: Optional[str] = None
    create_rule: Optional[str] = None
    update_rule: Optional[str] = None
    delete_rule: Optional[str] = None
    manage_rule: Optional[str] = None
    view_query: Optional[str] = None


class CollectionResponse(CollectionBase):
    """Schema for collection response."""

    id: str
    schema: List[FieldSchema]
    options: Dict[str, Any]

    list_rule: Optional[str]
    view_rule: Optional[str]
    create_rule: Optional[str]
    update_rule: Optional[str]
    delete_rule: Optional[str]
    manage_rule: Optional[str] = None
    view_query: Optional[str]

    system: bool
    created: datetime
    updated: datetime
    message: Optional[str] = None

    class Config:
        from_attributes = True


class CollectionListResponse(BaseModel):
    """Schema for collection list response."""

    items: List[CollectionResponse]
    total: int
    page: int
    per_page: int
    message: Optional[str] = None


class CollectionSchemaExport(BaseModel):
    """Schema for exporting collection as JSON."""

    name: str
    type: str
    fields: List[Dict[str, Any]] = Field(..., alias="schema")
    options: Dict[str, Any]
    list_rule: Optional[str]
    view_rule: Optional[str]
    create_rule: Optional[str]
    update_rule: Optional[str]
    delete_rule: Optional[str]
    manage_rule: Optional[str] = None
    view_query: Optional[str]
