"""
Public decorator API for user hook scripts (hooks/*.py drop-in files).

Usage in hooks/*.py files:
    from app.fastcms_hooks_api import on_record_create, on_record_update, on_record_delete

For full plugin packages (plugins/my_plugin/), use app.fastcms_plugin_api instead.
"""

from typing import Callable, Optional

from app.core.events import EventType, get_dispatcher
from app.core.logging import get_logger

logger = get_logger(__name__)


def _make_decorator(event_type: EventType, collection_name: Optional[str] = None):
    """Create a collection-scoped event decorator."""
    def decorator(func: Callable):
        dispatcher = get_dispatcher()

        async def handler(event):
            # Filter by collection if specified
            if collection_name and event.collection_name != collection_name:
                return
            await func(event)

        dispatcher.on(event_type, handler)
        logger.info(
            f"Hook registered: {func.__name__}() → {event_type.value}"
            + (f" (collection: {collection_name})" if collection_name else "")
        )
        return func
    return decorator


def on_record_create(collection_name: Optional[str] = None):
    """Decorator: fires after a record is created."""
    return _make_decorator(EventType.RECORD_CREATED, collection_name)


def on_record_update(collection_name: Optional[str] = None):
    """Decorator: fires after a record is updated."""
    return _make_decorator(EventType.RECORD_UPDATED, collection_name)


def on_record_delete(collection_name: Optional[str] = None):
    """Decorator: fires after a record is deleted."""
    return _make_decorator(EventType.RECORD_DELETED, collection_name)


def on_any_event():
    """Decorator: fires on all events."""
    def decorator(func: Callable):
        dispatcher = get_dispatcher()
        for event_type in EventType:
            dispatcher.on(event_type, func)
        logger.info(f"Hook registered: {func.__name__}() → all events")
        return func
    return decorator
