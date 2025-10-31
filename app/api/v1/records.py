"""API endpoints for dynamic record CRUD operations."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.record_service import RecordService
from app.schemas.record import (
    RecordCreate,
    RecordUpdate,
    RecordResponse,
    RecordListResponse,
    RecordFilter,
)
from app.core.dependencies import require_auth, get_optional_user_id


router = APIRouter()


@router.post(
    "/{collection_name}/records",
    response_model=RecordResponse,
    status_code=201,
    summary="Create a record",
)
async def create_record(
    collection_name: str = Path(..., description="Collection name"),
    data: RecordCreate = ...,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
):
    """Create a new record in the specified collection."""
    service = RecordService(db, collection_name)
    return await service.create_record(data)


@router.get(
    "/{collection_name}/records",
    response_model=RecordListResponse,
    summary="List records",
)
async def list_records(
    collection_name: str = Path(..., description="Collection name"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: Optional[str] = Query(None, description="Field to sort by"),
    order: str = Query("asc", description="Sort order (asc or desc)"),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """List all records in the specified collection with pagination."""
    service = RecordService(db, collection_name)
    return await service.list_records(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
    )


@router.get(
    "/{collection_name}/records/{record_id}",
    response_model=RecordResponse,
    summary="Get a record",
)
async def get_record(
    collection_name: str = Path(..., description="Collection name"),
    record_id: str = Path(..., description="Record ID"),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Get a specific record by ID."""
    service = RecordService(db, collection_name)
    return await service.get_record(record_id)


@router.patch(
    "/{collection_name}/records/{record_id}",
    response_model=RecordResponse,
    summary="Update a record",
)
async def update_record(
    collection_name: str = Path(..., description="Collection name"),
    record_id: str = Path(..., description="Record ID"),
    data: RecordUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
):
    """Update a specific record."""
    service = RecordService(db, collection_name)
    return await service.update_record(record_id, data)


@router.delete(
    "/{collection_name}/records/{record_id}",
    status_code=204,
    summary="Delete a record",
)
async def delete_record(
    collection_name: str = Path(..., description="Collection name"),
    record_id: str = Path(..., description="Record ID"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
):
    """Delete a specific record."""
    service = RecordService(db, collection_name)
    await service.delete_record(record_id)
    return None
