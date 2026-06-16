"""
Real-time Updates API using WebSockets and Pub/Sub.

This module provides a scalable real-time messaging system with:
- WebSocket connections with authentication
- Collection-based subscriptions with filtering
- Presence tracking (user joined/left)
- Server-initiated heartbeats
- Horizontal scaling via Redis Pub/Sub (or in-memory fallback)
"""

import uuid
from app.utils.timeutils import utcnow
from typing import Any, Dict, Optional

import orjson
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.events import Event, EventType
from app.core.logging import get_logger
from app.core.security import decode_token
from app.core.websocket_manager import connection_manager, Connection

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/realtime")
async def websocket_realtime(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time updates.

    **Connection:**
    ```
    ws://localhost:8000/api/v1/ws/realtime
    ws://localhost:8000/api/v1/ws/realtime?token=YOUR_JWT_TOKEN
    ```

    **Client Messages (JSON):**

    | Action | Example |
    |--------|---------|
    | Subscribe to collection | `{"action": "subscribe", "collection": "posts"}` |
    | Subscribe with filter | `{"action": "subscribe", "collection": "posts", "filter": {"published": true}}` |
    | Subscribe to all events | `{"action": "subscribe", "collection": "*"}` |
    | Unsubscribe | `{"action": "unsubscribe", "collection": "posts"}` |
    | Authenticate | `{"action": "auth", "token": "YOUR_JWT"}` |
    | Heartbeat response | `{"action": "pong"}` |

    **Server Messages (JSON):**

    | Type | Description |
    |------|-------------|
    | `connected` | Connection established |
    | `authenticated` | Authentication successful |
    | `subscribed` | Subscription confirmed |
    | `unsubscribed` | Unsubscription confirmed |
    | `event` | Real-time data event |
    | `ping` | Server heartbeat (respond with pong) |
    | `error` | Error message |
    | `presence` | User joined/left notification |
    """
    connection_id = str(uuid.uuid4())
    connection: Optional[Connection] = None

    try:
        # Accept and register connection
        connection = await connection_manager.connect(websocket, connection_id)

        # Authenticate if token provided
        if token:
            await _handle_auth(connection, token)

        # Main message loop
        while True:
            try:
                raw_data = await websocket.receive_text()
                message = orjson.loads(raw_data)

                # Update activity timestamp
                connection.update_activity()

                await _handle_message(connection, message)

            except orjson.JSONDecodeError:
                await connection.send_json({
                    "type": "error",
                    "data": {"message": "Invalid JSON format"}
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}", exc_info=True)
    finally:
        if connection:
            # Get user_id before disconnecting for presence tracking
            user_id = connection.user_id

            # Disconnect and cleanup
            await connection_manager.disconnect(connection_id)

            # Broadcast user left if authenticated
            if user_id:
                await _broadcast_presence(user_id, "left")


async def _handle_message(connection: Connection, message: Dict[str, Any]) -> None:
    """Handle an incoming WebSocket message."""
    action = message.get("action", "").lower()

    if action == "ping" or action == "pong":
        # Client heartbeat response
        connection.update_activity()
        if action == "ping":
            await connection.send_json({"type": "pong"})

    elif action == "auth":
        await _handle_auth(connection, message.get("token"))

    elif action == "subscribe":
        await _handle_subscribe(connection, message)

    elif action == "unsubscribe":
        await _handle_unsubscribe(connection, message)

    else:
        await connection.send_json({
            "type": "error",
            "data": {"message": f"Unknown action: {action}"}
        })


async def _handle_auth(connection: Connection, token: Optional[str]) -> None:
    """Handle authentication request."""
    if not token:
        await connection.send_json({
            "type": "error",
            "data": {"message": "Authentication token required"}
        })
        return

    try:
        payload = decode_token(token)
        if not payload or "sub" not in payload:
            await connection.send_json({
                "type": "error",
                "data": {"message": "Invalid or expired token"}
            })
            return

        user_id = payload["sub"]

        # Update connection with auth info
        await connection_manager.authenticate(connection.connection_id, user_id)

        await connection.send_json({
            "type": "authenticated",
            "data": {
                "user_id": user_id,
                "email": payload.get("email"),
            }
        })

        logger.info(f"Connection {connection.connection_id} authenticated as {user_id}")

        # Broadcast user joined
        await _broadcast_presence(user_id, "joined")

    except Exception as e:
        logger.error(f"Auth failed for {connection.connection_id}: {e}")
        await connection.send_json({
            "type": "error",
            "data": {"message": "Authentication failed"}
        })


async def _handle_subscribe(connection: Connection, message: Dict[str, Any]) -> None:
    """Handle subscription request."""
    collection = message.get("collection")

    if not collection:
        await connection.send_json({
            "type": "error",
            "data": {"message": "Collection name required for subscription"}
        })
        return

    filter_dict = message.get("filter")

    if collection == "*":
        await connection_manager.subscribe_global(connection.connection_id)
    else:
        await connection_manager.subscribe(
            connection.connection_id,
            collection,
            filter_dict
        )

    await connection.send_json({
        "type": "subscribed",
        "data": {
            "collection": collection,
            "filter": filter_dict,
        }
    })


async def _handle_unsubscribe(connection: Connection, message: Dict[str, Any]) -> None:
    """Handle unsubscription request."""
    collection = message.get("collection")

    if not collection:
        await connection.send_json({
            "type": "error",
            "data": {"message": "Collection name required for unsubscription"}
        })
        return

    await connection_manager.unsubscribe(connection.connection_id, collection)

    await connection.send_json({
        "type": "unsubscribed",
        "data": {"collection": collection}
    })


async def _broadcast_presence(user_id: str, action: str) -> None:
    """Broadcast a presence event (user joined/left)."""
    event_type = EventType.USER_JOINED if action == "joined" else EventType.USER_LEFT

    event = Event(
        type=event_type,
        collection_name="presence",
        record_id=user_id,
        data={
            "user_id": user_id,
            "action": action,
            "timestamp": utcnow().isoformat(),
        }
    )

    await connection_manager.broadcast_event(event.to_dict())


@router.get("/stats", summary="Real-time connection statistics")
async def get_realtime_stats() -> Dict[str, Any]:
    """
    Get real-time connection statistics for this server instance.

    **Note:** In a multi-server deployment, this returns stats only for
    the server handling this request. For cluster-wide stats, you would
    need to aggregate from all instances.

    **Response:**
    ```json
    {
        "total_connections": 10,
        "authenticated_connections": 8,
        "unique_users": 6,
        "pubsub_backend": "redis",
        "subscriptions": {
            "conn-id-1": ["posts", "comments"],
            "conn-id-2": ["*"]
        }
    }
    ```
    """
    return connection_manager.get_stats()
