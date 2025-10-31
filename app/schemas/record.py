"""Record schemas for dynamic CRUD operations."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class RecordCreate(BaseModel):
    """Schema for creating a record in any collection."""

    data: Dict[str, Any] = Field(..., description="Record data matching collection schema")

    @field_validator("data")
    @classmethod
    def validate_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("Record data cannot be empty")
        return v


class RecordUpdate(BaseModel):
    """Schema for updating a record in any collection."""

    data: Dict[str, Any] = Field(..., description="Fields to update")

    @field_validator("data")
    @classmethod
    def validate_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("Update data cannot be empty")
        return v


class RecordResponse(BaseModel):
    """Schema for record response."""

    id: str
    data: Dict[str, Any]
    created: datetime
    updated: datetime

    class Config:
        from_attributes = True


class RecordListResponse(BaseModel):
    """Schema for paginated record list."""

    items: List[RecordResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class RecordFilter(BaseModel):
    """Schema for filtering records."""

    field: str
    operator: str = Field(..., description="eq, ne, gt, lt, gte, lte, like, in")
    value: Any


class RecordQuery(BaseModel):
    """Schema for querying records with filters, sorting, and pagination."""

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    filters: Optional[List[RecordFilter]] = None
    sort: Optional[str] = Field(default=None, description="Field name to sort by")
    order: Optional[str] = Field(default="asc", description="asc or desc")

    @field_validator("order")
    @classmethod
    def validate_order(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["asc", "desc"]:
            raise ValueError("Order must be 'asc' or 'desc'")
        return v
