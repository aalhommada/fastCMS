"""
Pub/Sub Manager for Real-time Messaging.

This module provides a scalable publish/subscribe system that:
- Uses Redis for multi-server horizontal scaling
- Falls back to in-memory broadcasting for single-server deployments
- Handles smart subscription management with reference counting
"""

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import AsyncGenerator, Dict, Optional, Set
import orjson

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BasePubSub(ABC):
    """Abstract base class for Pub/Sub implementations."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the message broker."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and cleanup resources."""
        pass

    @abstractmethod
    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a channel."""
        pass

    @abstractmethod
    async def subscribe(self, channel: str) -> None:
        """Subscribe to a channel."""
        pass

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""
        pass

    @abstractmethod
    async def listen(self) -> AsyncGenerator[tuple[str, str], None]:
        """Listen for messages from subscribed channels. Yields (channel, message) tuples."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to the message broker."""
        pass


class InMemoryPubSub(BasePubSub):
    """
    In-memory Pub/Sub for single-server deployments.

    This implementation uses asyncio queues for message delivery,
    suitable for development or single-instance production.
    """

    def __init__(self):
        self._subscriptions: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._connected = True
        logger.info("In-memory Pub/Sub initialized (single-server mode)")

    async def disconnect(self) -> None:
        self._connected = False
        self._subscriptions.clear()
        logger.info("In-memory Pub/Sub disconnected")

    async def publish(self, channel: str, message: str) -> None:
        if not self._connected:
            return
        await self._message_queue.put((channel, message))

    async def subscribe(self, channel: str) -> None:
        pass  # No-op for in-memory, handled by listen()

    async def unsubscribe(self, channel: str) -> None:
        pass  # No-op for in-memory

    async def listen(self) -> AsyncGenerator[tuple[str, str], None]:
        while self._connected:
            try:
                channel, message = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )
                yield channel, message
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"In-memory Pub/Sub listen error: {e}")
                await asyncio.sleep(0.1)

    def is_connected(self) -> bool:
        return self._connected


class RedisPubSub(BasePubSub):
    """
    Redis-backed Pub/Sub for multi-server horizontal scaling.

    Features:
    - Reference-counted subscriptions (deduplicate channel subscriptions)
    - Automatic reconnection handling
    - Clean subscription management
    """

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None
        self._pubsub = None
        self._subscribed_channels: Dict[str, int] = {}  # channel -> reference count
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        try:
            from redis.asyncio import Redis

            logger.info(f"Connecting to Redis at {self.redis_url}")
            self._redis = Redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )

            # Test connection
            if not await self._redis.ping():
                raise ConnectionError("Redis PING failed")

            self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            logger.info("Redis Pub/Sub connected successfully")

        except ImportError:
            logger.error("redis package not installed. Run: uv tool install 'pyfastcms[redis]'")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis = None
            self._pubsub = None
            raise

    async def disconnect(self) -> None:
        if self._pubsub:
            try:
                await self._pubsub.close()
            except Exception:
                pass
            self._pubsub = None

        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None

        self._subscribed_channels.clear()
        logger.info("Redis Pub/Sub disconnected")

    async def publish(self, channel: str, message: str) -> None:
        if not self._redis:
            logger.warning("Cannot publish: Redis not connected")
            return

        try:
            await self._redis.publish(channel, message)
            logger.debug(f"Published to {channel}")
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")

    async def subscribe(self, channel: str) -> None:
        """Subscribe to a channel with reference counting."""
        if not self._pubsub:
            return

        async with self._lock:
            if channel in self._subscribed_channels:
                # Already subscribed, increment reference count
                self._subscribed_channels[channel] += 1
                logger.debug(f"Incremented ref count for {channel}: {self._subscribed_channels[channel]}")
            else:
                # New subscription
                try:
                    await self._pubsub.subscribe(channel)
                    self._subscribed_channels[channel] = 1
                    logger.info(f"Subscribed to Redis channel: {channel}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {channel}: {e}")

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel with reference counting."""
        if not self._pubsub:
            return

        async with self._lock:
            if channel in self._subscribed_channels:
                self._subscribed_channels[channel] -= 1

                if self._subscribed_channels[channel] <= 0:
                    # No more references, actually unsubscribe
                    try:
                        await self._pubsub.unsubscribe(channel)
                        del self._subscribed_channels[channel]
                        logger.info(f"Unsubscribed from Redis channel: {channel}")
                    except Exception as e:
                        logger.error(f"Failed to unsubscribe from {channel}: {e}")

    async def listen(self) -> AsyncGenerator[tuple[str, str], None]:
        if not self._pubsub:
            return

        while self._redis:
            try:
                message = await self._pubsub.get_message(timeout=1.0)
                if message and message.get("type") == "message":
                    channel = message.get("channel", "")
                    data = message.get("data", "")
                    if data:
                        yield channel, data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Redis listen error: {e}")
                await asyncio.sleep(1)

    def is_connected(self) -> bool:
        return self._redis is not None


class PubSubManager:
    """
    Unified Pub/Sub Manager that abstracts the underlying implementation.

    Automatically selects Redis or In-Memory based on configuration.
    Provides a consistent interface regardless of the backend.
    """

    def __init__(self):
        self._backend: Optional[BasePubSub] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the appropriate Pub/Sub backend."""
        if self._initialized:
            return

        if settings.REDIS_ENABLED:
            try:
                self._backend = RedisPubSub(settings.REDIS_URL)
                await self._backend.connect()
                logger.info("Pub/Sub using Redis backend (multi-server mode)")
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to in-memory: {e}")
                self._backend = InMemoryPubSub()
                await self._backend.connect()
        else:
            self._backend = InMemoryPubSub()
            await self._backend.connect()

        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown the Pub/Sub backend."""
        if self._backend:
            await self._backend.disconnect()
            self._backend = None
        self._initialized = False

    async def publish(self, channel: str, message: dict) -> None:
        """Publish a message (dict) to a channel."""
        if not self._backend:
            await self.initialize()

        json_message = orjson.dumps(message).decode("utf-8")
        await self._backend.publish(channel, json_message)

    async def subscribe(self, channel: str) -> None:
        """Subscribe to a channel."""
        if not self._backend:
            await self.initialize()
        await self._backend.subscribe(channel)

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""
        if self._backend:
            await self._backend.unsubscribe(channel)

    async def listen(self) -> AsyncGenerator[tuple[str, dict], None]:
        """Listen for messages. Yields (channel, parsed_message) tuples."""
        if not self._backend:
            await self.initialize()

        async for channel, raw_message in self._backend.listen():
            try:
                message = orjson.loads(raw_message)
                yield channel, message
            except Exception as e:
                logger.error(f"Failed to parse message from {channel}: {e}")

    def is_connected(self) -> bool:
        """Check if the backend is connected."""
        return self._backend is not None and self._backend.is_connected()

    @property
    def backend_type(self) -> str:
        """Return the type of backend being used."""
        if isinstance(self._backend, RedisPubSub):
            return "redis"
        elif isinstance(self._backend, InMemoryPubSub):
            return "memory"
        return "none"


# Global Pub/Sub manager instance
pubsub_manager = PubSubManager()


async def get_pubsub_manager() -> PubSubManager:
    """Get the initialized Pub/Sub manager."""
    if not pubsub_manager._initialized:
        await pubsub_manager.initialize()
    return pubsub_manager
