"""
Event Broadcaster for Real-time Updates.

This module provides the event abstraction and broadcasting system.
Events are published to the Pub/Sub system and also trigger webhooks.
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Type alias for hook handler functions
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


class EventType(str, Enum):
    """Types of events that can be broadcast."""

    # Record events
    RECORD_CREATED = "record.created"
    RECORD_UPDATED = "record.updated"
    RECORD_DELETED = "record.deleted"

    # Collection events
    COLLECTION_CREATED = "collection.created"
    COLLECTION_UPDATED = "collection.updated"
    COLLECTION_DELETED = "collection.deleted"

    # Presence events
    USER_JOINED = "user.joined"
    USER_LEFT = "user.left"


class Event:
    """
    Represents a real-time event.

    Attributes:
        type: The event type (record.created, etc.)
        collection_name: The collection this event relates to
        record_id: Optional ID of the affected record
        data: The event payload data
        timestamp: When the event occurred
    """

    def __init__(
        self,
        type: EventType,
        collection_name: str,
        data: Dict[str, Any],
        record_id: Optional[str] = None,
    ):
        self.type = type
        self.collection_name = collection_name
        self.record_id = record_id
        self.data = data
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the event to a dictionary."""
        return {
            "type": self.type.value,
            "collection": self.collection_name,
            "record_id": self.record_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Deserialize an event from a dictionary."""
        event = cls(
            type=EventType(data["type"]),
            collection_name=data["collection"],
            record_id=data.get("record_id"),
            data=data["data"],
        )
        event.timestamp = data.get("timestamp", event.timestamp)
        return event

    def __repr__(self) -> str:
        return f"Event({self.type.value}, {self.collection_name}, {self.record_id})"


class EventDispatcher:
    """
    In-process event dispatcher — routes events to registered hook handlers.

    Handlers are async callables: ``async def handler(event: Event) -> None``.
    """

    def __init__(self):
        self._handlers: dict[EventType, List[EventHandler]] = defaultdict(list)
        self._global_handlers: List[EventHandler] = []

    def on(self, event_type: EventType, handler: EventHandler) -> None:
        """Register *handler* to fire when *event_type* is dispatched."""
        self._handlers[event_type].append(handler)

    def on_all(self, handler: EventHandler) -> None:
        """Register *handler* to fire on every event regardless of type."""
        self._global_handlers.append(handler)

    async def dispatch(self, event: "Event") -> None:
        """Call all handlers registered for the event's type, plus global ones."""
        handlers = self._handlers.get(event.type, []) + self._global_handlers
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Hook handler '{handler.__name__}' raised an error "
                    f"for event {event.type.value} on '{event.collection_name}': {e}",
                    exc_info=True,
                )


# Global dispatcher singleton — shared between hook_loader and EventBroadcaster
_dispatcher = EventDispatcher()


def get_dispatcher() -> EventDispatcher:
    """Return the global EventDispatcher instance."""
    return _dispatcher


class EventBroadcaster:
    """
    Broadcasts events to real-time clients and triggers webhooks.

    This is a stateless service that:
    1. Publishes events to the WebSocket connection manager (via Pub/Sub)
    2. Triggers webhook deliveries asynchronously
    """

    async def broadcast(self, event: Event) -> None:
        """
        Broadcast an event to all subscribers.

        Args:
            event: The event to broadcast
        """
        logger.debug(f"Broadcasting event: {event}")

        # 1. Dispatch to in-process user hook handlers
        asyncio.create_task(_dispatcher.dispatch(event))

        # 2. Publish to WebSocket clients via connection manager
        try:
            from app.core.websocket_manager import connection_manager
            await connection_manager.broadcast_event(event.to_dict())
        except Exception as e:
            logger.error(f"Failed to broadcast to WebSocket clients: {e}")

        # 3. Trigger webhooks asynchronously (fire and forget)
        asyncio.create_task(self._trigger_webhooks(event))

    async def broadcast_record_event(
        self,
        event_type: EventType,
        collection_name: str,
        record_id: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Convenience method to broadcast a record event.

        Args:
            event_type: Type of record event
            collection_name: Name of the collection
            record_id: ID of the affected record
            data: Record data
        """
        event = Event(
            type=event_type,
            collection_name=collection_name,
            record_id=record_id,
            data=data,
        )
        await self.broadcast(event)

    async def broadcast_collection_event(
        self,
        event_type: EventType,
        collection_name: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Convenience method to broadcast a collection event.

        Args:
            event_type: Type of collection event
            collection_name: Name of the collection
            data: Collection metadata
        """
        event = Event(
            type=event_type,
            collection_name=collection_name,
            data=data,
        )
        await self.broadcast(event)

    async def _trigger_webhooks(self, event: Event) -> None:
        """
        Trigger webhook deliveries for an event.
        Runs in background to not block the main flow.
        """
        try:
            from app.db.session import async_session_maker
            from app.services.webhook_service import WebhookService

            async with async_session_maker() as db:
                webhook_service = WebhookService(db)
                await webhook_service.deliver_event(
                    collection_name=event.collection_name,
                    event_type=event.type.value,
                    record_id=event.record_id or "",
                    data=event.data,
                )
        except Exception as e:
            logger.error(f"Webhook delivery failed for {event}: {e}")


# Global event broadcaster instance
event_manager = EventBroadcaster()
