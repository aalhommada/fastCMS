"""
FastCMS client — sync (FastCMS) and async (AsyncFastCMS).

Both share the same service API; the only difference is that
AsyncFastCMS methods are coroutines.
"""
from __future__ import annotations

from typing import Any

import httpx

from .auth import AuthService, AsyncAuthService
from .collection import CollectionClient, AsyncCollectionClient
from .exceptions import AuthError, FastCMSError, NetworkError, NotFoundError, ValidationError
from .files import FilesService, AsyncFilesService
from .realtime import AsyncRealtimeService, RealtimeService


def _raise_for_status(response: httpx.Response) -> dict | None:
    """Convert HTTP error responses into typed exceptions."""
    if response.status_code < 400:
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    try:
        body = response.json()
    except Exception:
        body = {"detail": response.text}

    message = body.get("detail") or body.get("message") or str(body)

    if response.status_code in (401, 403):
        raise AuthError(message, status=response.status_code, data=body)
    if response.status_code == 404:
        raise NotFoundError(message)
    if response.status_code == 422:
        raise ValidationError(message, fields=body.get("errors"))
    raise FastCMSError(message, status=response.status_code, data=body)


class FastCMS:
    """
    Synchronous FastCMS client.

    Usage::

        cms = FastCMS("http://localhost:8000", api_key="sk-...")
        posts = cms.collection("posts").get_list(filter="published=true")
        me = cms.auth.sign_in("user@example.com", "password")
    """

    def __init__(self, base_url: str, *, api_key: str | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._tokens: dict | None = None
        self._timeout = timeout

        self.auth = AuthService(self)
        self.files = FilesService(self)
        self.realtime = RealtimeService(self)

    # ── Auth helpers ────────────────────────────────────────────────────────

    def _set_tokens(self, data: dict) -> None:
        self._tokens = {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
        }

    def clear_auth(self) -> None:
        self._tokens = None

    # ── Collection factory ──────────────────────────────────────────────────

    def collection(self, name: str) -> CollectionClient:
        return CollectionClient(self, name)

    # ── HTTP helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        headers: dict[str, str] = {}
        if self._tokens and self._tokens.get("access_token"):
            headers["Authorization"] = f"Bearer {self._tokens['access_token']}"
        elif self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = self.base_url + path
        try:
            response = httpx.request(
                method,
                url,
                headers=self._headers(),
                timeout=self._timeout,
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise NetworkError(f"Request failed: {exc}") from exc
        return _raise_for_status(response)

    def _get(self, path: str, **kw) -> Any:
        return self._request("GET", path, **kw)

    def _post(self, path: str, **kw) -> Any:
        return self._request("POST", path, **kw)

    def _patch(self, path: str, **kw) -> Any:
        return self._request("PATCH", path, **kw)

    def _put(self, path: str, **kw) -> Any:
        return self._request("PUT", path, **kw)

    def _delete(self, path: str, **kw) -> Any:
        return self._request("DELETE", path, **kw)


class AsyncFastCMS:
    """
    Asynchronous FastCMS client (all service methods are coroutines).

    Usage::

        async with AsyncFastCMS("http://localhost:8000") as cms:
            await cms.auth.sign_in("user@example.com", "password")
            posts = await cms.collection("posts").get_list()
    """

    def __init__(self, base_url: str, *, api_key: str | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._tokens: dict | None = None
        self._timeout = timeout
        self._http: httpx.AsyncClient | None = None

        self.auth = AsyncAuthService(self)
        self.files = AsyncFilesService(self)
        self.realtime = AsyncRealtimeService(self)

    async def __aenter__(self) -> "AsyncFastCMS":
        self._http = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *args) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ── Auth helpers ────────────────────────────────────────────────────────

    def _set_tokens(self, data: dict) -> None:
        self._tokens = {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
        }

    def clear_auth(self) -> None:
        self._tokens = None

    # ── Collection factory ──────────────────────────────────────────────────

    def collection(self, name: str) -> AsyncCollectionClient:
        return AsyncCollectionClient(self, name)

    # ── HTTP helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        headers: dict[str, str] = {}
        if self._tokens and self._tokens.get("access_token"):
            headers["Authorization"] = f"Bearer {self._tokens['access_token']}"
        elif self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = self.base_url + path
        http = self._http or httpx.AsyncClient(timeout=self._timeout)
        own_client = self._http is None

        try:
            response = await http.request(method, url, headers=self._headers(), **kwargs)
        except httpx.RequestError as exc:
            raise NetworkError(f"Request failed: {exc}") from exc
        finally:
            if own_client:
                await http.aclose()

        return _raise_for_status(response)

    async def _get(self, path: str, **kw) -> Any:
        return await self._request("GET", path, **kw)

    async def _post(self, path: str, **kw) -> Any:
        return await self._request("POST", path, **kw)

    async def _patch(self, path: str, **kw) -> Any:
        return await self._request("PATCH", path, **kw)

    async def _put(self, path: str, **kw) -> Any:
        return await self._request("PUT", path, **kw)

    async def _delete(self, path: str, **kw) -> Any:
        return await self._request("DELETE", path, **kw)
