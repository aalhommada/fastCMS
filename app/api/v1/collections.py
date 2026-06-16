"""
API endpoints for collection management.
"""

from typing import Any, List, Optional
import json

from fastapi import APIRouter, Depends, Query, Response, status, Path, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
import io

from app.core.dependencies import require_auth, require_admin, require_auth_context, UserContext
from app.core.exceptions import ForbiddenException
from app.db.session import get_db
from app.schemas.collection import (
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)
from app.services.collection_service import CollectionService


# ===== Index API Schemas =====

class IndexField(BaseModel):
    """Field configuration for an index."""
    name: str = Field(..., description="Field name")
    order: str = Field(default="asc", description="Sort order: asc or desc")


class IndexCreate(BaseModel):
    """Schema for creating a new index."""
    name: str = Field(..., min_length=1, max_length=100, description="Index name")
    fields: List[IndexField] = Field(..., min_length=1, description="Fields to index")
    unique: bool = Field(default=False, description="Whether the index should enforce uniqueness")


class IndexResponse(BaseModel):
    """Response schema for an index."""
    name: str
    fields: List[IndexField]
    unique: bool
    created: bool = True


class IndexListResponse(BaseModel):
    """Response schema for listing indexes."""
    items: List[IndexResponse]
    total: int

router = APIRouter()


@router.post(
    "",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new collection",
    description="Create a new collection with dynamic schema. Requires authentication.",
)
async def create_collection(
    data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_auth_context),
) -> CollectionResponse:
    """
    Create a new collection.

    Args:
        data: Collection creation data
        db: Database session
        user: Authenticated user context

    Returns:
        Created collection
    """
    # View collections execute an arbitrary view_query as raw SQL (CREATE VIEW ...),
    # which can read any table. Restrict creating them to admins.
    if data.type == "view" and user.role != "admin":
        raise ForbiddenException("Only admins can create view collections")
    service = CollectionService(db)
    return await service.create_collection(data)


@router.get(
    "",
    response_model=CollectionListResponse,
    summary="List all collections",
    description="Get a paginated list of all collections. Requires authentication.",
)
async def list_collections(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=200, description="Items per page"),
    include_system: bool = Query(False, description="Include system collections"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
) -> CollectionListResponse:
    """
    List all collections with pagination.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page (max 200)
        include_system: Include system collections
        db: Database session

    Returns:
        Paginated list of collections
    """
    service = CollectionService(db)
    collections, total = await service.list_collections(
        page=page,
        per_page=per_page,
        include_system=include_system,
    )

    return CollectionListResponse(
        items=collections,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{collection_id}",
    response_model=CollectionResponse,
    summary="Get a collection by ID",
    description="Retrieve a single collection by its ID.",
)
async def get_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """
    Get collection by ID.

    Args:
        collection_id: Collection ID
        db: Database session

    Returns:
        Collection data
    """
    service = CollectionService(db)
    return await service.get_collection(collection_id)


@router.patch(
    "/{collection_id}",
    response_model=CollectionResponse,
    summary="Update a collection",
    description="Update collection schema, rules, or options. Requires authentication.",
)
async def update_collection(
    collection_id: str,
    data: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_auth_context),
) -> CollectionResponse:
    """
    Update a collection.

    Args:
        collection_id: Collection ID
        data: Update data
        db: Database session
        user: Authenticated user context

    Returns:
        Updated collection
    """
    # Setting/changing a view_query runs raw SQL (CREATE VIEW ...). Admins only.
    if data.view_query is not None and user.role != "admin":
        raise ForbiddenException("Only admins can set a view query")
    service = CollectionService(db)
    return await service.update_collection(collection_id, data)


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a collection",
    description="Delete a collection and its associated table. Requires authentication.",
)
async def delete_collection(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
) -> None:
    """
    Delete a collection.

    Args:
        collection_id: Collection ID
        db: Database session
        user_id: Authenticated user ID
    """
    service = CollectionService(db)
    await service.delete_collection(collection_id)


@router.get(
    "/name/{collection_name}",
    response_model=CollectionResponse,
    summary="Get a collection by name",
    description="Retrieve a single collection by its name.",
)
async def get_collection_by_name(
    collection_name: str,
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """
    Get collection by name.

    Args:
        collection_name: Collection name
        db: Database session

    Returns:
        Collection data
    """
    service = CollectionService(db)
    return await service.get_collection_by_name(collection_name)


@router.get(
    "/{collection_id}/export",
    summary="Export collection",
    description="Export collection schema and optionally data as JSON. Admin only.",
)
async def export_collection(
    collection_id: str,
    include_data: bool = Query(False, description="Include collection records in export"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """
    Export a collection as JSON.

    - Exports collection schema
    - Optionally exports all records
    - Returns downloadable JSON file
    """
    service = CollectionService(db)
    collection = await service.get_collection(collection_id)

    export_data = {
        "name": collection.name,
        "type": collection.type,
        "schema": collection.schema,
        "list_rule": collection.list_rule,
        "view_rule": collection.view_rule,
        "create_rule": collection.create_rule,
        "update_rule": collection.update_rule,
        "delete_rule": collection.delete_rule,
        "indexes": collection.indexes or [],
        "system": collection.system,
    }

    # Include records if requested
    if include_data:
        from app.services.record_service import RecordService

        record_service = RecordService(db)
        records_response = await record_service.list_records(
            collection_name=collection.name,
            page=1,
            per_page=10000,  # Export up to 10k records
        )
        export_data["records"] = [
            {
                "id": record.id,
                "data": record.data,
                "created": record.created.isoformat() if record.created else None,
                "updated": record.updated.isoformat() if record.updated else None,
            }
            for record in records_response.items
        ]

    # Create JSON response
    json_str = json.dumps(export_data, indent=2)
    buffer = io.BytesIO(json_str.encode())

    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={collection.name}_export.json"
        },
    )


@router.post(
    "/import",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import collection",
    description="Import a collection from JSON export. Admin only.",
)
async def import_collection(
    data: dict,
    import_records: bool = Query(
        False, description="Import records along with collection"
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """
    Import a collection from JSON export.

    - Creates collection from schema
    - Optionally imports records
    - Returns created collection
    """
    service = CollectionService(db)

    # Extract collection data
    collection_data = CollectionCreate(
        name=data["name"],
        type=data.get("type", "base"),
        schema=data["schema"],
        list_rule=data.get("list_rule"),
        view_rule=data.get("view_rule"),
        create_rule=data.get("create_rule"),
        update_rule=data.get("update_rule"),
        delete_rule=data.get("delete_rule"),
        indexes=data.get("indexes", []),
    )

    # Create collection
    collection = await service.create_collection(collection_data)

    # Import records if requested
    if import_records and "records" in data:
        from app.services.record_service import RecordService

        record_service = RecordService(db)

        for record in data["records"]:
            try:
                await record_service.create_record(
                    collection_name=collection.name, data=record["data"]
                )
            except Exception as e:
                # Log but continue importing other records
                print(f"Failed to import record: {str(e)}")
                continue

    return collection


# ===== Custom Index API =====

@router.get(
    "/{collection_id}/indexes",
    response_model=IndexListResponse,
    summary="List collection indexes",
    description="List all indexes defined on a collection. Requires authentication.",
)
async def list_indexes(
    collection_id: str = Path(..., description="Collection ID"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
) -> IndexListResponse:
    """
    List all indexes on a collection.

    Returns both custom indexes and system indexes.
    """
    service = CollectionService(db)
    collection = await service.get_collection(collection_id)

    # Get indexes from collection schema
    indexes = collection.indexes or []

    items = [
        IndexResponse(
            name=idx.get("name", f"idx_{i}"),
            fields=[IndexField(**f) for f in idx.get("fields", [])],
            unique=idx.get("unique", False),
        )
        for i, idx in enumerate(indexes)
    ]

    return IndexListResponse(items=items, total=len(items))


@router.post(
    "/{collection_id}/indexes",
    response_model=IndexResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an index",
    description="Create a new index on a collection. Requires authentication.",
)
async def create_index(
    collection_id: str = Path(..., description="Collection ID"),
    data: IndexCreate = ...,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
) -> IndexResponse:
    """
    Create a new index on a collection.

    The index will be created in the database immediately.

    Example request:
    ```json
    {
        "name": "idx_title_created",
        "fields": [
            {"name": "title", "order": "asc"},
            {"name": "created", "order": "desc"}
        ],
        "unique": false
    }
    ```
    """
    service = CollectionService(db)
    collection = await service.get_collection(collection_id)

    # Check if index with same name exists
    existing_indexes = collection.indexes or []
    for idx in existing_indexes:
        if idx.get("name") == data.name:
            raise HTTPException(
                status_code=400,
                detail=f"Index '{data.name}' already exists"
            )

    # Create index in database
    table_name = collection.name
    field_list = ", ".join([
        f"{f.name} {'DESC' if f.order == 'desc' else 'ASC'}"
        for f in data.fields
    ])

    unique_clause = "UNIQUE" if data.unique else ""
    sql = f"CREATE {unique_clause} INDEX IF NOT EXISTS {data.name} ON {table_name} ({field_list})"

    try:
        await db.execute(text(sql))
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create index: {str(e)}")

    # Add to collection metadata
    new_index = {
        "name": data.name,
        "fields": [f.model_dump() for f in data.fields],
        "unique": data.unique,
    }
    updated_indexes = existing_indexes + [new_index]

    # Update collection with new index
    from app.schemas.collection import CollectionUpdate
    await service.update_collection(
        collection_id,
        CollectionUpdate(indexes=updated_indexes)
    )

    return IndexResponse(
        name=data.name,
        fields=data.fields,
        unique=data.unique,
        created=True,
    )


@router.delete(
    "/{collection_id}/indexes/{index_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an index",
    description="Delete an index from a collection. Requires authentication.",
)
async def delete_index(
    collection_id: str = Path(..., description="Collection ID"),
    index_name: str = Path(..., description="Index name"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
) -> None:
    """
    Delete an index from a collection.

    This removes the index from both the database and collection metadata.
    """
    service = CollectionService(db)
    collection = await service.get_collection(collection_id)

    # Check if index exists in metadata
    existing_indexes = collection.indexes or []
    found = False
    updated_indexes = []

    for idx in existing_indexes:
        if idx.get("name") == index_name:
            found = True
        else:
            updated_indexes.append(idx)

    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Index '{index_name}' not found"
        )

    # Drop index from database
    try:
        await db.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to drop index: {str(e)}")

    # Update collection metadata
    from app.schemas.collection import CollectionUpdate
    await service.update_collection(
        collection_id,
        CollectionUpdate(indexes=updated_indexes)
    )


@router.get(
    "/{collection_id}/indexes/{index_name}",
    response_model=IndexResponse,
    summary="Get index details",
    description="Get details of a specific index. Requires authentication.",
)
async def get_index(
    collection_id: str = Path(..., description="Collection ID"),
    index_name: str = Path(..., description="Index name"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_auth),
) -> IndexResponse:
    """
    Get details of a specific index.
    """
    service = CollectionService(db)
    collection = await service.get_collection(collection_id)

    # Find index in metadata
    indexes = collection.indexes or []
    for idx in indexes:
        if idx.get("name") == index_name:
            return IndexResponse(
                name=idx.get("name"),
                fields=[IndexField(**f) for f in idx.get("fields", [])],
                unique=idx.get("unique", False),
            )

    raise HTTPException(
        status_code=404,
        detail=f"Index '{index_name}' not found"
    )


@router.delete(
    "/name/{collection_name}/truncate",
    summary="Truncate a collection",
    description="Delete all records in a collection without dropping the table. Requires admin.",
)
async def truncate_collection(
    collection_name: str = Path(..., description="Collection name"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
) -> dict:
    """Delete all records in a collection (admin only)."""
    service = CollectionService(db)
    return await service.truncate_collection(collection_name)
