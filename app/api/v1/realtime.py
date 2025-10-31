"""Real-time updates API using Server-Sent Events (SSE)."""
import asyncio
from typing import Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from app.core.events import event_manager, Event
from app.core.dependencies import get_optional_user_id


router = APIRouter()


async def event_generator(
    request: Request,
    collection_name: Optional[str] = None,
):
    """
    Generate Server-Sent Events.

    Args:
        request: FastAPI request (to detect client disconnect)
        collection_name: Optional collection to subscribe to

    Yields:
        SSE formatted messages
    """
    # Subscribe to events
    queue = await event_manager.subscribe(collection_name)

    try:
        # Send initial connection message
        yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"

        while True:
            # Check if client is still connected
            if await request.is_disconnected():
                break

            try:
                # Wait for events with timeout to allow disconnect detection
                event: Event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield event.to_sse_message()
            except asyncio.TimeoutError:
                # Send keep-alive comment to prevent connection timeout
                yield ": keep-alive\n\n"
                continue

    finally:
        # Cleanup on disconnect
        await event_manager.unsubscribe(queue, collection_name)


@router.get(
    "/realtime",
    summary="Subscribe to real-time updates (all collections)",
)
async def realtime_all(
    request: Request,
    user_id: Optional[str] = Query(None),
):
    """
    Subscribe to real-time updates for all collections.

    This endpoint uses Server-Sent Events (SSE) to push updates to the client.

    Example usage (JavaScript):
    ```javascript
    const eventSource = new EventSource('/api/v1/realtime');

    eventSource.addEventListener('record.created', (e) => {
        const data = JSON.parse(e.data);
        console.log('Record created:', data);
    });

    eventSource.addEventListener('record.updated', (e) => {
        const data = JSON.parse(e.data);
        console.log('Record updated:', data);
    });

    eventSource.addEventListener('record.deleted', (e) => {
        const data = JSON.parse(e.data);
        console.log('Record deleted:', data);
    });
    ```
    """
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/realtime/{collection_name}",
    summary="Subscribe to real-time updates (specific collection)",
)
async def realtime_collection(
    collection_name: str,
    request: Request,
    user_id: Optional[str] = Query(None),
):
    """
    Subscribe to real-time updates for a specific collection.

    This endpoint uses Server-Sent Events (SSE) to push updates to the client.

    Example usage (JavaScript):
    ```javascript
    const eventSource = new EventSource('/api/v1/realtime/posts');

    eventSource.addEventListener('record.created', (e) => {
        const data = JSON.parse(e.data);
        console.log('New post created:', data);
    });

    eventSource.addEventListener('record.updated', (e) => {
        const data = JSON.parse(e.data);
        console.log('Post updated:', data);
    });

    eventSource.addEventListener('record.deleted', (e) => {
        const data = JSON.parse(e.data);
        console.log('Post deleted:', data);
    });
    ```
    """
    return StreamingResponse(
        event_generator(request, collection_name),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
