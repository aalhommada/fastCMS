"""Repository for webhook delivery logs."""

from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.webhook_delivery import WebhookDelivery


class WebhookDeliveryRepository:
    """Repository for webhook delivery log CRUD."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, delivery: WebhookDelivery) -> WebhookDelivery:
        self.db.add(delivery)
        await self.db.flush()
        return delivery

    async def get_by_webhook(
        self, webhook_id: str, skip: int = 0, limit: int = 50
    ) -> List[WebhookDelivery]:
        stmt = (
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(desc(WebhookDelivery.created))
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, skip: int = 0, limit: int = 50) -> List[WebhookDelivery]:
        stmt = (
            select(WebhookDelivery)
            .order_by(desc(WebhookDelivery.created))
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_webhook(self, webhook_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(WebhookDelivery)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
