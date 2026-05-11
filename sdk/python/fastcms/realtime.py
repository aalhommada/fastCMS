"""
Real-time SSE subscriptions.

Sync version: spawns a daemon thread for each subscription.
Async version: uses an async generator (requires ``httpx-sse`` package).
"""
from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .client import FastCMS, AsyncFastCMS


class RealtimeService:
    """Sync SSE subscription using background daemon threads."""

    def __init__(self, client: "FastCMS"):
        self._client = client
        self._threads: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}

    def subscribe(
        self,
        collection_name: str,
        callback: Callable[[dict], None],
        *,
        filter: str | None = None,
    ) -> Callable[[], None]:
        """
        Subscribe to real-time events for *collection_name*.

        Runs an SSE listener in a background daemon thread.
        Returns an ``unsubscribe`` callable.

        Requires ``httpx`` and ``httpx-sse``.
        """
        try:
            import httpx
            from httpx_sse import connect_sse  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("Realtime requires: uv pip install httpx httpx-sse (or pip install)") from exc

        key = f"{collection_name}-{id(callback)}"
        stop_event = threading.Event()
        self._stop_events[key] = stop_event

        def _run():
            params = {}
            if filter: params["filter"] = filter
            tokens = self._client._tokens
            if tokens and tokens.get("access_token"):
                params["token"] = tokens["access_token"]

            url = f"{self._client.base_url}/api/v1/realtime/{collection_name}"
            try:
                with httpx.Client(timeout=None) as http:
                    with connect_sse(http, "GET", url, params=params) as source:
                        for event in source.iter_sse():
                            if stop_event.is_set():
                                break
                            try:
                                callback(json.loads(event.data))
                            except Exception:
                                pass
            except Exception:
                pass  # Connection closed / stopped

        t = threading.Thread(target=_run, daemon=True, name=f"fastcms-sse-{key}")
        t.start()
        self._threads[key] = t

        def unsubscribe():
            stop_event.set()
            self._threads.pop(key, None)
            self._stop_events.pop(key, None)

        return unsubscribe

    def close_all(self):
        for event in self._stop_events.values():
            event.set()
        self._threads.clear()
        self._stop_events.clear()


class AsyncRealtimeService:
    """Async SSE subscription using httpx streaming."""

    def __init__(self, client: "AsyncFastCMS"):
        self._client = client

    async def subscribe(
        self,
        collection_name: str,
        callback: Callable[[dict], None],
        *,
        filter: str | None = None,
    ):
        """
        Async generator that yields SSE events.

        Usage::

            async for event in client.realtime.subscribe("posts"):
                print(event)

        Requires ``httpx`` and ``httpx-sse``.
        """
        try:
            import httpx
            from httpx_sse import aconnect_sse  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("Realtime requires: uv pip install httpx httpx-sse (or pip install)") from exc

        params = {}
        if filter: params["filter"] = filter
        tokens = self._client._tokens
        if tokens and tokens.get("access_token"):
            params["token"] = tokens["access_token"]

        url = f"{self._client.base_url}/api/v1/realtime/{collection_name}"
        async with httpx.AsyncClient(timeout=None) as http:
            async with aconnect_sse(http, "GET", url, params=params) as source:
                async for event in source.aiter_sse():
                    try:
                        yield json.loads(event.data)
                    except Exception:
                        pass
