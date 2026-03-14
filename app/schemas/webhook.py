"""Pydantic schemas for webhook endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""

    url: str = Field(..., description="Webhook URL")
    collection_name: str = Field(..., description="Collection to subscribe to")
    events: List[str] = Field(
        ..., description="Event types to subscribe to (create, update, delete, *)"
    )
    secret: Optional[str] = Field(None, description="Secret for HMAC signature")
    retry_count: int = Field(default=3, ge=0, le=10, description="Number of retries on failure")
    active: bool = Field(default=True, description="Whether webhook is active immediately")


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook."""

    url: Optional[str] = Field(None, description="Webhook URL")
    events: Optional[List[str]] = Field(None, description="Event types to subscribe to")
    active: Optional[bool] = Field(None, description="Whether webhook is active")
    secret: Optional[str] = Field(None, description="Secret for HMAC signature")
    retry_count: Optional[int] = Field(None, ge=0, le=10, description="Number of retries")


class WebhookResponse(BaseModel):
    """Schema for webhook response."""

    id: str
    url: str
    collection_name: str
    events: str
    active: bool
    secret: Optional[str]
    retry_count: int
    last_triggered_at: Optional[str]
    created: datetime
    updated: datetime

    class Config:
        from_attributes = True


class WebhookListResponse(BaseModel):
    """Schema for paginated webhook list."""

    items: List[WebhookResponse]
    total: int


class WebhookDeliveryResponse(BaseModel):
    """Schema for a webhook delivery log entry."""

    id: str
    webhook_id: str
    event_type: str
    record_id: str
    url: str
    status_code: Optional[int]
    response_body: Optional[str]
    attempt: int
    success: bool
    duration_ms: Optional[int]
    error: Optional[str]
    created: datetime

    class Config:
        from_attributes = True


class WebhookDeliveryListResponse(BaseModel):
    """Schema for paginated delivery log list."""

    items: List[WebhookDeliveryResponse]
    total: int
