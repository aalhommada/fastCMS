"""API endpoints for webhook management."""

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import UserContext, require_auth_context
from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.schemas.webhook import (
    WebhookCreate,
    WebhookListResponse,
    WebhookResponse,
    WebhookUpdate,
)
from app.services.webhook_service import WebhookService

router = APIRouter()


@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a webhook",
)
async def create_webhook(
    data: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(require_auth_context),
) -> WebhookResponse:
    """
    Create a new webhook subscription.
    Requires authentication.
    """
    service = WebhookService(db)
    webhook = await service.create_webhook(
        url=data.url,
        collection_name=data.collection_name,
        events=data.events,
        secret=data.secret,
        retry_count=data.retry_count,
        active=data.active,
    )
    return WebhookResponse.model_validate(webhook)


@router.get(
    "/webhooks",
    response_model=WebhookListResponse,
    summary="List webhooks",
)
async def list_webhooks(
    collection_name: Optional[str] = Query(None, description="Filter by collection"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(require_auth_context),
) -> WebhookListResponse:
    """
    List all webhooks with optional filtering.
    Requires authentication.
    """
    service = WebhookService(db)
    webhooks = await service.list_webhooks(
        collection_name=collection_name, skip=skip, limit=limit
    )
    return WebhookListResponse(
        items=[WebhookResponse.model_validate(w) for w in webhooks],
        total=len(webhooks),
    )


@router.get(
    "/webhooks/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get a webhook",
)
async def get_webhook(
    webhook_id: str = Path(..., description="Webhook ID"),
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(require_auth_context),
) -> WebhookResponse:
    """
    Get webhook by ID.
    Requires authentication.
    """
    service = WebhookService(db)
    webhook = await service.get_webhook(webhook_id)

    if not webhook:
        raise NotFoundException(f"Webhook '{webhook_id}' not found")

    return WebhookResponse.model_validate(webhook)


@router.patch(
    "/webhooks/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update a webhook",
)
async def update_webhook(
    webhook_id: str = Path(..., description="Webhook ID"),
    data: WebhookUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(require_auth_context),
) -> WebhookResponse:
    """
    Update webhook configuration.
    Requires authentication.
    """
    service = WebhookService(db)
    webhook = await service.update_webhook(
        webhook_id=webhook_id,
        url=data.url,
        events=data.events,
        active=data.active,
        secret=data.secret,
        retry_count=data.retry_count,
    )

    if not webhook:
        raise NotFoundException(f"Webhook '{webhook_id}' not found")

    return WebhookResponse.model_validate(webhook)


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook",
)
async def delete_webhook(
    webhook_id: str = Path(..., description="Webhook ID"),
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(require_auth_context),
) -> None:
    """
    Delete a webhook.
    Requires authentication.
    """
    service = WebhookService(db)
    success = await service.delete_webhook(webhook_id)

    if not success:
        raise NotFoundException(f"Webhook '{webhook_id}' not found")
