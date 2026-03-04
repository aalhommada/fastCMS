"""
Internal hooks utilities for service-layer before/after event patterns.

For user hook scripts (hooks/*.py): use app.fastcms_hooks_api
For plugin packages (plugins/*/): use app.fastcms_plugin_api
"""
from typing import Callable, Awaitable, Any, Dict, Optional
from app.core.events import Event, EventHandler, EventType, get_dispatcher
from app.core.logging import get_logger

logger = get_logger(__name__)


class HookContext:
    """
    Context manager for emitting events with before/after pattern

    Usage:
        async with HookContext(EventType.RECORD_BEFORE_CREATE, data=record_data):
            # Create record
            record = await create_record(...)
        # After event automatically fired
    """

    def __init__(
        self,
        before_event: EventType,
        after_event: Optional[EventType] = None,
        collection_name: Optional[str] = None,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.before_event = before_event
        self.after_event = after_event
        self.collection_name = collection_name
        self.record_id = record_id
        self.user_id = user_id
        self.data = data or {}
        self.metadata = metadata or {}
        self.dispatcher = get_dispatcher()
        self.result = None

    async def __aenter__(self):
        """Fire before event"""
        event = Event(
            type=self.before_event,
            data=self.data,
            collection_name=self.collection_name or "",
            record_id=self.record_id,
        )
        await self.dispatcher.dispatch(event)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Fire after event if provided and no exception"""
        if exc_type is None and self.after_event:
            # Add result to data if set
            data = self.data.copy()
            if self.result is not None:
                data["result"] = self.result

            event = Event(
                type=self.after_event,
                data=data,
                collection_name=self.collection_name or "",
                record_id=self.record_id,
            )
            await self.dispatcher.dispatch(event)

    def set_result(self, result: Any) -> None:
        """Set the result to include in after event"""
        self.result = result


async def emit_event(
    event_type: EventType,
    collection_name: Optional[str] = None,
    record_id: Optional[str] = None,
    user_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit an event manually

    Args:
        event_type: Type of event
        collection_name: Optional collection name
        record_id: Optional record ID
        user_id: Optional user ID
        data: Event data
        metadata: Event metadata
    """
    dispatcher = get_dispatcher()
    event = Event(
        type=event_type,
        data=data or {},
        collection_name=collection_name or "",
        record_id=record_id,
    )
    await dispatcher.dispatch(event)


# Convenience functions for common patterns


async def with_hooks(
    before: EventType,
    after: EventType,
    operation: Callable[[], Awaitable[Any]],
    collection_name: Optional[str] = None,
    record_id: Optional[str] = None,
    user_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Execute an operation with before/after hooks

    Args:
        before: Before event type
        after: After event type
        operation: Async function to execute
        collection_name: Optional collection name
        record_id: Optional record ID
        user_id: Optional user ID
        data: Event data

    Returns:
        Result of the operation
    """
    async with HookContext(
        before_event=before,
        after_event=after,
        collection_name=collection_name,
        record_id=record_id,
        user_id=user_id,
        data=data,
    ) as ctx:
        result = await operation()
        ctx.set_result(result)
        return result
