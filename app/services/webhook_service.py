"""Service for webhook management and delivery."""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.webhook import Webhook
from app.db.repositories.webhook import WebhookRepository

logger = get_logger(__name__)


class WebhookService:
    """Service for managing and delivering webhooks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = WebhookRepository(db)

    async def create_webhook(
        self,
        url: str,
        collection_name: str,
        events: List[str],
        secret: Optional[str] = None,
        retry_count: int = 3,
        active: bool = True,
    ) -> Webhook:
        """Create a new webhook subscription."""
        webhook = Webhook(
            url=url,
            collection_name=collection_name,
            events=",".join(events),
            secret=secret,
            retry_count=retry_count,
            active=active,
        )

        webhook = await self.repo.create(webhook)
        await self.db.commit()

        logger.info(
            f"Webhook created for collection '{collection_name}' to URL: {url}"
        )
        return webhook

    async def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        """Get webhook by ID."""
        return await self.repo.get_by_id(webhook_id)

    async def list_webhooks(
        self, collection_name: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Webhook]:
        """List webhooks with optional filtering."""
        if collection_name:
            return await self.repo.get_by_collection(collection_name, active_only=False)
        return await self.repo.get_all(skip=skip, limit=limit)

    async def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        events: Optional[List[str]] = None,
        active: Optional[bool] = None,
        secret: Optional[str] = None,
        retry_count: Optional[int] = None,
    ) -> Optional[Webhook]:
        """Update webhook configuration."""
        webhook = await self.repo.get_by_id(webhook_id)
        if not webhook:
            return None

        if url is not None:
            webhook.url = url
        if events is not None:
            webhook.events = ",".join(events)
        if active is not None:
            webhook.active = active
        if secret is not None:
            webhook.secret = secret
        if retry_count is not None:
            webhook.retry_count = retry_count

        webhook = await self.repo.update(webhook)
        await self.db.commit()

        logger.info(f"Webhook {webhook_id} updated")
        return webhook

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete webhook."""
        success = await self.repo.delete(webhook_id)
        if success:
            await self.db.commit()
            logger.info(f"Webhook {webhook_id} deleted")
        return success

    async def deliver_event(
        self, collection_name: str, event_type: str, record_id: str, data: Dict[str, Any]
    ) -> None:
        """Deliver webhook event to all subscribed webhooks."""
        webhooks = await self.repo.get_by_collection(collection_name, active_only=True)

        for webhook in webhooks:
            # Check if webhook is subscribed to this event type
            subscribed_events = webhook.events.split(",")
            if event_type not in subscribed_events and "*" not in subscribed_events:
                continue

            # Deliver webhook asynchronously
            await self._deliver_webhook(webhook, event_type, record_id, data)

    async def _deliver_webhook(
        self, webhook: Webhook, event_type: str, record_id: str, data: Dict[str, Any]
    ) -> None:
        """Deliver a single webhook with retry logic."""
        payload = {
            "event": event_type,
            "collection": webhook.collection_name,
            "record_id": record_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        headers = {"Content-Type": "application/json"}

        # Add signature if secret is configured
        if webhook.secret:
            signature = self._generate_signature(json.dumps(payload), webhook.secret)
            headers["X-Webhook-Signature"] = signature

        # Try delivery with retries
        success = False
        for attempt in range(webhook.retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        webhook.url, json=payload, headers=headers
                    )

                    if response.status_code < 500:
                        success = True
                        webhook.last_triggered_at = datetime.now(timezone.utc).isoformat()
                        await self.repo.update(webhook)
                        await self.db.commit()

                        if response.status_code >= 400:
                            logger.warning(
                                f"Webhook {webhook.id} returned {response.status_code}"
                            )
                        else:
                            logger.info(
                                f"Webhook delivered successfully to {webhook.url}"
                            )
                        break

            except Exception as e:
                logger.error(
                    f"Webhook delivery attempt {attempt + 1} failed: {str(e)}"
                )
                if attempt == webhook.retry_count:
                    logger.error(
                        f"Webhook {webhook.id} failed after {webhook.retry_count} retries"
                    )

        if not success:
            # Optionally deactivate webhook after multiple failures
            # webhook.active = False
            # await self.repo.update(webhook)
            # await self.db.commit()
            pass

    @staticmethod
    def _generate_signature(payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        return hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
