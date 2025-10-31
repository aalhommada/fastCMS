"""Event manager for real-time updates using Server-Sent Events (SSE)."""
import asyncio
import json
from typing import Dict, Set, Optional, Any
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """Types of events that can be broadcast."""

    RECORD_CREATED = "record.created"
    RECORD_UPDATED = "record.updated"
    RECORD_DELETED = "record.deleted"
    COLLECTION_CREATED = "collection.created"
    COLLECTION_UPDATED = "collection.updated"
    COLLECTION_DELETED = "collection.deleted"


class Event:
    """Event data structure."""

    def __init__(
        self,
        event_type: EventType,
        collection_name: str,
        data: Dict[str, Any],
        record_id: Optional[str] = None,
    ):
        self.event_type = event_type
        self.collection_name = collection_name
        self.data = data
        self.record_id = record_id
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "type": self.event_type,
            "collection": self.collection_name,
            "record_id": self.record_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    def to_sse_message(self) -> str:
        """Format as SSE message."""
        data = json.dumps(self.to_dict())
        return f"event: {self.event_type}\ndata: {data}\n\n"


class EventManager:
    """Manages SSE connections and event broadcasting."""

    def __init__(self):
        # Collection name -> set of queues
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # Global subscribers (all events)
        self._global_subscribers: Set[asyncio.Queue] = set()

    async def subscribe(
        self, collection_name: Optional[str] = None
    ) -> asyncio.Queue:
        """
        Subscribe to events.

        Args:
            collection_name: Subscribe to specific collection, or None for all events

        Returns:
            Queue that will receive events
        """
        queue = asyncio.Queue()

        if collection_name:
            if collection_name not in self._subscribers:
                self._subscribers[collection_name] = set()
            self._subscribers[collection_name].add(queue)
        else:
            self._global_subscribers.add(queue)

        return queue

    async def unsubscribe(
        self, queue: asyncio.Queue, collection_name: Optional[str] = None
    ):
        """Unsubscribe from events."""
        if collection_name:
            if collection_name in self._subscribers:
                self._subscribers[collection_name].discard(queue)
                if not self._subscribers[collection_name]:
                    del self._subscribers[collection_name]
        else:
            self._global_subscribers.discard(queue)

    async def broadcast(self, event: Event):
        """
        Broadcast an event to all relevant subscribers.

        Args:
            event: Event to broadcast
        """
        # Send to collection-specific subscribers
        if event.collection_name in self._subscribers:
            for queue in self._subscribers[event.collection_name].copy():
                try:
                    await queue.put(event)
                except Exception:
                    # Remove dead subscriber
                    self._subscribers[event.collection_name].discard(queue)

        # Send to global subscribers
        for queue in self._global_subscribers.copy():
            try:
                await queue.put(event)
            except Exception:
                # Remove dead subscriber
                self._global_subscribers.discard(queue)

    def get_subscriber_count(self, collection_name: Optional[str] = None) -> int:
        """Get number of active subscribers."""
        if collection_name:
            return len(self._subscribers.get(collection_name, set()))
        return len(self._global_subscribers)


# Global event manager instance
event_manager = EventManager()
