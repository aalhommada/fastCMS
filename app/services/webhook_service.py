"""Service for webhook management and delivery."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.webhook import Webhook
from app.db.models.webhook_delivery import WebhookDelivery
from app.db.repositories.webhook import WebhookRepository
from app.db.repositories.webhook_delivery import WebhookDeliveryRepository

logger = get_logger(__name__)

# Exponential backoff base delay (seconds). Retries: 1s, 2s, 4s, 8s, 16s...
BACKOFF_BASE = 1
BACKOFF_MAX = 30


class WebhookService:
    """Service for managing and delivering webhooks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = WebhookRepository(db)
        self.delivery_repo = WebhookDeliveryRepository(db)

    # ------------------------------------------------------------------
    # Webhook CRUD
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

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
        """Deliver a single webhook with retry logic and exponential backoff."""
        payload = {
            "event": event_type,
            "collection": webhook.collection_name,
            "record_id": record_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        headers = {"Content-Type": "application/json"}

        # Add HMAC-SHA256 signature if secret is configured
        payload_str = json.dumps(payload)
        if webhook.secret:
            signature = self._generate_signature(payload_str, webhook.secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Try delivery with retries + exponential backoff
        success = False
        for attempt in range(webhook.retry_count + 1):
            # Exponential backoff: skip delay on first attempt
            if attempt > 0:
                delay = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_MAX)
                logger.info(
                    f"Webhook {webhook.id} retry {attempt} in {delay}s"
                )
                await asyncio.sleep(delay)

            start = time.monotonic()
            status_code = None
            response_body = None
            error_msg = None

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        webhook.url, json=payload, headers=headers
                    )
                    status_code = response.status_code
                    response_body = response.text[:500]  # truncate

                    if response.status_code < 500:
                        success = True
                        webhook.last_triggered_at = datetime.now(timezone.utc).isoformat()
                        await self.repo.update(webhook)

                        if response.status_code >= 400:
                            logger.warning(
                                f"Webhook {webhook.id} returned {response.status_code}"
                            )
                        else:
                            logger.info(
                                f"Webhook delivered successfully to {webhook.url}"
                            )

            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"Webhook delivery attempt {attempt + 1} failed: {error_msg}"
                )

            duration_ms = int((time.monotonic() - start) * 1000)

            # Log every delivery attempt
            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event_type=event_type,
                record_id=record_id,
                url=webhook.url,
                status_code=status_code,
                response_body=response_body,
                attempt=attempt + 1,
                success=success,
                duration_ms=duration_ms,
                error=error_msg,
            )
            await self.delivery_repo.create(delivery)
            await self.db.commit()

            if success:
                break

            if attempt == webhook.retry_count:
                logger.error(
                    f"Webhook {webhook.id} failed after {webhook.retry_count + 1} attempts"
                )

    # ------------------------------------------------------------------
    # Delivery logs
    # ------------------------------------------------------------------

    async def list_deliveries(
        self,
        webhook_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[WebhookDelivery]:
        """List delivery logs, optionally filtered by webhook."""
        if webhook_id:
            return await self.delivery_repo.get_by_webhook(webhook_id, skip, limit)
        return await self.delivery_repo.get_recent(skip, limit)

    async def count_deliveries(self, webhook_id: Optional[str] = None) -> int:
        if webhook_id:
            return await self.delivery_repo.count_by_webhook(webhook_id)
        return await self.delivery_repo.count_all()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_signature(payload: str, secret: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload."""
        return hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
