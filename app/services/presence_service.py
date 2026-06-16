"""Presence tracking service for realtime features."""
import asyncio
from app.utils.timeutils import utcnow
from typing import Dict, Set, Optional, Any
from datetime import timedelta
from collections import defaultdict

from app.core.logging import get_logger
from app.core.events import Event, EventType

logger = get_logger(__name__)


class PresenceStatus:
    """Presence status constants."""
    ONLINE = "online"
    OFFLINE = "offline"
    TYPING = "typing"
    IDLE = "idle"
    AWAY = "away"


class PresenceInfo:
    """Information about a user's presence."""
    
    def __init__(self, user_id: str, collection: str, status: str = PresenceStatus.ONLINE):
        self.user_id = user_id
        self.collection = collection
        self.status = status
        self.last_seen = utcnow()
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "collection": self.collection,
            "status": self.status,
            "last_seen": self.last_seen.isoformat(),
            "metadata": self.metadata
        }
    
    def update_status(self, status: str, metadata: Optional[Dict[str, Any]] = None):
        """Update presence status."""
        self.status = status
        self.last_seen = utcnow()
        if metadata:
            self.metadata.update(metadata)


class PresenceService:
    """Manages user presence tracking."""
    
    def __init__(self):
        # collection -> user_id -> PresenceInfo
        self._presence: Dict[str, Dict[str, PresenceInfo]] = defaultdict(dict)
        
        # user_id -> set of collections
        self._user_collections: Dict[str, Set[str]] = defaultdict(set)
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def join(
        self,
        user_id: str,
        collection: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PresenceInfo:
        """Mark user as online in a collection."""
        async with self._lock:
            if user_id not in self._presence[collection]:
                presence = PresenceInfo(user_id, collection)
                self._presence[collection][user_id] = presence
                self._user_collections[user_id].add(collection)
            else:
                presence = self._presence[collection][user_id]
                presence.update_status(PresenceStatus.ONLINE, metadata)
        
        logger.info(f"User {user_id} joined {collection}")
        
        # Broadcast presence event
        await self._broadcast_presence(presence, "join")
        
        return presence
    
    async def leave(self, user_id: str, collection: str):
        """Mark user as offline in a collection."""
        async with self._lock:
            if user_id in self._presence[collection]:
                presence = self._presence[collection][user_id]
                presence.update_status(PresenceStatus.OFFLINE)
                
                # Remove from tracking
                del self._presence[collection][user_id]
                self._user_collections[user_id].discard(collection)
                
                if not self._user_collections[user_id]:
                    del self._user_collections[user_id]
                
                logger.info(f"User {user_id} left {collection}")
                
                # Broadcast presence event
                await self._broadcast_presence(presence, "leave")
    
    async def update_status(
        self,
        user_id: str,
        collection: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update user's presence status."""
        async with self._lock:
            if user_id in self._presence[collection]:
                presence = self._presence[collection][user_id]
                presence.update_status(status, metadata)
                
                logger.debug(f"User {user_id} status updated to {status} in {collection}")
                
                # Broadcast presence event
                await self._broadcast_presence(presence, "update")
    
    async def get_online_users(self, collection: str) -> list[Dict[str, Any]]:
        """Get all online users in a collection."""
        return [
            presence.to_dict()
            for presence in self._presence[collection].values()
            if presence.status != PresenceStatus.OFFLINE
        ]
    
    async def get_user_presence(self, user_id: str, collection: str) -> Optional[PresenceInfo]:
        """Get presence info for a specific user in a collection."""
        return self._presence[collection].get(user_id)
    
    async def cleanup_stale(self, max_idle_minutes: int = 30):
        """Remove stale presence entries."""
        now = utcnow()
        cutoff = now - timedelta(minutes=max_idle_minutes)
        
        to_remove = []
        
        async with self._lock:
            for collection, users in self._presence.items():
                for user_id, presence in users.items():
                    if presence.last_seen < cutoff:
                        to_remove.append((collection, user_id))
        
        for collection, user_id in to_remove:
            await self.leave(user_id, collection)
            logger.info(f"Removed stale presence for user {user_id} in {collection}")
    
    async def _broadcast_presence(self, presence: PresenceInfo, event_type: str):
        """Broadcast presence event to WebSocket connections."""
        try:
            from app.core.websocket_manager import connection_manager
            
            message = {
                "type": "presence",
                "data": {
                    "event": event_type,
                    **presence.to_dict()
                },
                "timestamp": utcnow().isoformat()
            }
            
            await connection_manager.broadcast_to_collection(
                presence.collection,
                message
            )
        except Exception as e:
            logger.error(f"Error broadcasting presence: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get presence statistics."""
        total_users = sum(len(users) for users in self._presence.values())
        
        return {
            "total_online_users": total_users,
            "collections": {
                collection: len(users)
                for collection, users in self._presence.items()
            }
        }


# Global presence service instance
presence_service = PresenceService()
