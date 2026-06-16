"""
WebSocket Connection Manager for Real-time Features.

This module provides a production-ready WebSocket connection manager with:
- Heartbeat monitoring and automatic cleanup of stale connections
- Smart subscription management per connection
- Filter-based message delivery
- Presence tracking
- Integration with the Pub/Sub backend for horizontal scaling
"""

import asyncio
from app.utils.timeutils import utcnow
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket

from app.core.logging import get_logger
from app.core.pubsub import pubsub_manager

logger = get_logger(__name__)

# Configuration
HEARTBEAT_INTERVAL = 30  # seconds between server pings
HEARTBEAT_TIMEOUT = 90  # seconds before considering connection dead
CLEANUP_INTERVAL = 60  # seconds between cleanup runs


class Connection:
    """Represents a single WebSocket connection with its state and metadata."""

    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.user_id: Optional[str] = None
        self.authenticated: bool = False
        self.connected_at: datetime = utcnow()
        self.last_activity: datetime = utcnow()

        # Subscriptions: collection_name -> filter_dict (None means no filter)
        self.subscriptions: Dict[str, Optional[Dict[str, Any]]] = {}
        self.is_global_subscriber: bool = False

        # Message queue for backpressure handling
        self._send_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._send_task: Optional[asyncio.Task] = None
        self._closed: bool = False

    def start_sender(self) -> None:
        """Start the background sender task for this connection."""
        if self._send_task is None:
            self._send_task = asyncio.create_task(self._sender_loop())

    async def _sender_loop(self) -> None:
        """Background task that processes the send queue."""
        while not self._closed:
            try:
                data = await asyncio.wait_for(self._send_queue.get(), timeout=1.0)
                await self.websocket.send_json(data)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if not self._closed:
                    logger.debug(f"Send failed for {self.connection_id}: {e}")
                break

    async def send_json(self, data: Dict[str, Any]) -> bool:
        """
        Queue a JSON message for sending.
        Returns False if the queue is full (backpressure).
        """
        if self._closed:
            return False

        try:
            self._send_queue.put_nowait(data)
            return True
        except asyncio.QueueFull:
            logger.warning(f"Message queue full for {self.connection_id}, dropping message")
            return False

    async def send_immediate(self, data: Dict[str, Any]) -> None:
        """Send a message immediately, bypassing the queue. Use for critical messages."""
        if not self._closed:
            try:
                await self.websocket.send_json(data)
            except Exception as e:
                logger.debug(f"Immediate send failed for {self.connection_id}: {e}")

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = utcnow()

    def is_stale(self, timeout_seconds: int = HEARTBEAT_TIMEOUT) -> bool:
        """Check if the connection is stale (no activity for too long)."""
        return utcnow() - self.last_activity > timedelta(seconds=timeout_seconds)

    def matches_event(self, collection: str, event_data: Dict[str, Any]) -> bool:
        """Check if an event matches this connection's subscriptions and filters."""
        # Global subscribers get everything
        if self.is_global_subscriber:
            return self._matches_filter("*", event_data)

        # Check specific collection subscription
        if collection in self.subscriptions:
            return self._matches_filter(collection, event_data)

        return False

    def _matches_filter(self, collection: str, event_data: Dict[str, Any]) -> bool:
        """Check if event data matches the filter for a collection."""
        filter_dict = self.subscriptions.get(collection)
        if not filter_dict:
            return True  # No filter means match all

        # Simple equality filter matching
        record_data = event_data.get("data", {})
        for key, value in filter_dict.items():
            if record_data.get(key) != value:
                return False

        return True

    async def close(self) -> None:
        """Close the connection and cleanup resources."""
        self._closed = True
        if self._send_task:
            self._send_task.cancel()
            try:
                await self._send_task
            except asyncio.CancelledError:
                pass


class ConnectionManager:
    """
    Manages WebSocket connections with Pub/Sub integration.

    Features:
    - Connection lifecycle management
    - Subscription handling with filters
    - Heartbeat monitoring and cleanup
    - Integration with Pub/Sub for event distribution
    """

    def __init__(self):
        self._connections: Dict[str, Connection] = {}
        self._user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self._lock = asyncio.Lock()

        # Background tasks
        self._listener_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the connection manager background tasks."""
        if self._running:
            return

        self._running = True

        # Start Pub/Sub listener
        self._listener_task = asyncio.create_task(self._pubsub_listener())

        # Start heartbeat sender
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Connection manager started")

    async def stop(self) -> None:
        """Stop the connection manager and cleanup."""
        self._running = False

        # Cancel background tasks
        for task in [self._listener_task, self._heartbeat_task, self._cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all connections
        async with self._lock:
            for conn in list(self._connections.values()):
                await conn.close()
            self._connections.clear()
            self._user_connections.clear()

        logger.info("Connection manager stopped")

    async def connect(self, websocket: WebSocket, connection_id: str) -> Connection:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        connection = Connection(websocket, connection_id)
        connection.start_sender()

        async with self._lock:
            self._connections[connection_id] = connection

        # Ensure background tasks are running
        if not self._running:
            await self.start()

        # Send connection confirmation
        await connection.send_immediate({
            "type": "connected",
            "data": {
                "connection_id": connection_id,
                "server_time": utcnow().isoformat(),
            }
        })

        logger.info(f"Client connected: {connection_id} (total: {len(self._connections)})")
        return connection

    async def disconnect(self, connection_id: str) -> Optional[str]:
        """
        Disconnect a client and cleanup resources.
        Returns the user_id if the connection was authenticated.
        """
        user_id = None

        async with self._lock:
            connection = self._connections.pop(connection_id, None)
            if connection:
                user_id = connection.user_id
                await connection.close()

                # Unsubscribe from Pub/Sub channels
                for collection in connection.subscriptions:
                    await pubsub_manager.unsubscribe(f"collection:{collection}")
                if connection.is_global_subscriber:
                    await pubsub_manager.unsubscribe("global:events")

                # Remove from user tracking
                if user_id and user_id in self._user_connections:
                    self._user_connections[user_id].discard(connection_id)
                    if not self._user_connections[user_id]:
                        del self._user_connections[user_id]

        logger.info(f"Client disconnected: {connection_id} (total: {len(self._connections)})")
        return user_id

    async def authenticate(self, connection_id: str, user_id: str) -> bool:
        """Mark a connection as authenticated."""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.user_id = user_id
            connection.authenticated = True

            # Track user connections
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)

        return True

    async def subscribe(
        self,
        connection_id: str,
        collection: str,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Subscribe a connection to a collection channel."""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.subscriptions[collection] = filter_dict

        # Subscribe to Pub/Sub channel
        await pubsub_manager.subscribe(f"collection:{collection}")

        logger.debug(f"Connection {connection_id} subscribed to '{collection}'")
        return True

    async def subscribe_global(self, connection_id: str) -> bool:
        """Subscribe a connection to all events."""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.is_global_subscriber = True
            connection.subscriptions["*"] = None

        # Subscribe to global Pub/Sub channel
        await pubsub_manager.subscribe("global:events")

        logger.debug(f"Connection {connection_id} subscribed globally")
        return True

    async def unsubscribe(self, connection_id: str, collection: str) -> bool:
        """Unsubscribe a connection from a collection channel."""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            if collection == "*":
                connection.is_global_subscriber = False
                connection.subscriptions.pop("*", None)
                await pubsub_manager.unsubscribe("global:events")
            elif collection in connection.subscriptions:
                del connection.subscriptions[collection]
                await pubsub_manager.unsubscribe(f"collection:{collection}")

        return True

    async def broadcast_event(self, event_dict: Dict[str, Any]) -> None:
        """Broadcast an event through the Pub/Sub system."""
        collection = event_dict.get("collection", "")

        # Publish to collection-specific channel
        await pubsub_manager.publish(f"collection:{collection}", event_dict)

        # Publish to global channel
        await pubsub_manager.publish("global:events", event_dict)

    async def _pubsub_listener(self) -> None:
        """Listen for messages from Pub/Sub and distribute to local connections."""
        logger.info("Pub/Sub listener started")

        try:
            async for channel, event_dict in pubsub_manager.listen():
                if not self._running:
                    break

                # Two channels carry every event:
                #   collection:X   → for connections subscribed to a specific collection
                #   global:events  → for connections subscribed to "*"
                # Each connection should receive the event ONCE — dispatch by
                # channel type so we don't double-deliver to a connection that
                # is subscribed both ways.
                if channel.startswith("collection:"):
                    collection = channel[11:]
                    is_global_channel = False
                elif channel == "global:events":
                    collection = event_dict.get("collection", "")
                    is_global_channel = True
                else:
                    continue

                # Get snapshot of connections
                async with self._lock:
                    connections = list(self._connections.values())

                # Deliver to matching connections — but only those whose
                # subscription mode matches this channel.
                for conn in connections:
                    if is_global_channel:
                        if not conn.is_global_subscriber:
                            continue
                    else:
                        # Specific-collection channel: skip global subscribers
                        # (they get the event via global:events instead).
                        if conn.is_global_subscriber:
                            continue
                        if collection not in conn.subscriptions:
                            continue

                    if conn.matches_event(collection, event_dict):
                        await conn.send_json({
                            "type": "event",
                            "data": event_dict,
                            "timestamp": utcnow().isoformat()
                        })

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Pub/Sub listener error: {e}", exc_info=True)

        logger.info("Pub/Sub listener stopped")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to all connections."""
        logger.info("Heartbeat task started")

        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                async with self._lock:
                    connections = list(self._connections.values())

                for conn in connections:
                    await conn.send_json({"type": "ping", "timestamp": utcnow().isoformat()})

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

        logger.info("Heartbeat task stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically cleanup stale connections."""
        logger.info("Cleanup task started")

        while self._running:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL)

                stale_ids = []
                async with self._lock:
                    for conn_id, conn in self._connections.items():
                        if conn.is_stale():
                            stale_ids.append(conn_id)

                for conn_id in stale_ids:
                    logger.warning(f"Cleaning up stale connection: {conn_id}")
                    await self.disconnect(conn_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

        logger.info("Cleanup task stopped")

    def get_connection(self, connection_id: str) -> Optional[Connection]:
        """Get a connection by ID."""
        return self._connections.get(connection_id)

    def get_user_connections(self, user_id: str) -> List[Connection]:
        """Get all connections for a user."""
        conn_ids = self._user_connections.get(user_id, set())
        return [self._connections[cid] for cid in conn_ids if cid in self._connections]

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics for this server instance."""
        authenticated = sum(1 for c in self._connections.values() if c.authenticated)
        subscriptions = {}
        for conn in self._connections.values():
            if conn.is_global_subscriber:
                subscriptions[conn.connection_id] = ["*"]
            else:
                subscriptions[conn.connection_id] = list(conn.subscriptions.keys())

        return {
            "total_connections": len(self._connections),
            "authenticated_connections": authenticated,
            "unique_users": len(self._user_connections),
            "pubsub_backend": pubsub_manager.backend_type,
            "subscriptions": subscriptions,
        }


# Global connection manager instance
connection_manager = ConnectionManager()
