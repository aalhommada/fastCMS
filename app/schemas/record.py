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
    expand: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class RecordListResponse(BaseModel):
    """Schema for paginated record list."""

    items: List[RecordResponse]
    total: Optional[int] = None
    page: int
    per_page: int
    total_pages: Optional[int] = None


class RecordFilter(BaseModel):
    """Schema for filtering records."""

    field: str
    operator: str = Field(
        ...,
        description=(
            "Filter operator. Standard: eq, ne, gt, lt, gte, lte, like, not_like. "
            "Array/Any: any_eq, any_ne, any_gt, any_lt, any_gte, any_lte, any_like, any_not_like"
        )
    )
    value: Any
    modifiers: Optional[List[str]] = Field(
        default=None,
        description="Field modifiers like :lower, :upper, :length, :isset, :excerpt(N)"
    )


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


class BulkDeleteRequest(BaseModel):
    """Schema for bulk deleting records."""

    record_ids: List[str] = Field(..., description="List of record IDs to delete", min_length=1)

    @field_validator("record_ids")
    @classmethod
    def validate_record_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one record ID is required")
        if len(v) > 100:
            raise ValueError("Cannot delete more than 100 records at once")
        return v


class BulkUpdateRequest(BaseModel):
    """Schema for bulk updating records."""

    record_ids: List[str] = Field(..., description="List of record IDs to update", min_length=1)
    data: Dict[str, Any] = Field(..., description="Fields to update on all records")

    @field_validator("record_ids")
    @classmethod
    def validate_record_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one record ID is required")
        if len(v) > 100:
            raise ValueError("Cannot update more than 100 records at once")
        return v

    @field_validator("data")
    @classmethod
    def validate_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("Update data cannot be empty")
        return v


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation response."""

    success: int = Field(..., description="Number of successfully processed records")
    failed: int = Field(..., description="Number of failed records")
    errors: Optional[List[Dict[str, str]]] = Field(default=None, description="List of errors for failed records")
