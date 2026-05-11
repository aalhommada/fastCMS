"""
Collection client — typed CRUD + batch + realtime subscribe.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generic, Iterator, TypeVar

if TYPE_CHECKING:
    from .client import FastCMS, AsyncFastCMS

T = TypeVar("T", bound=dict)


class CollectionClient(Generic[T]):
    """Synchronous typed collection client."""

    def __init__(self, client: "FastCMS", name: str):
        self._client = client
        self._name = name

    @property
    def _base(self) -> str:
        return f"/api/v1/{self._name}/records"

    def get_list(
        self,
        *,
        filter: str | None = None,
        sort: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        expand: str | None = None,
        fields: str | None = None,
        skip_total: bool = False,
    ) -> dict:
        """Return paginated record list: {items, page, per_page, total, total_pages}."""
        params: dict[str, Any] = {}
        if filter:    params["filter"] = filter
        if sort:      params["sort"] = sort
        if page:      params["page"] = page
        if per_page:  params["per_page"] = per_page
        if expand:    params["expand"] = expand
        if fields:    params["fields"] = fields
        if skip_total: params["skip_total"] = "true"
        return self._client._get(self._base, params=params)

    def get_one(self, record_id: str, *, expand: str | None = None, fields: str | None = None) -> T:
        params: dict[str, Any] = {}
        if expand: params["expand"] = expand
        if fields: params["fields"] = fields
        return self._client._get(f"{self._base}/{record_id}", params=params)

    def create(self, data: dict, *, expand: str | None = None) -> T:
        params = {"expand": expand} if expand else {}
        return self._client._post(self._base, json=data, params=params)

    def update(self, record_id: str, data: dict, *, expand: str | None = None) -> T:
        params = {"expand": expand} if expand else {}
        return self._client._patch(f"{self._base}/{record_id}", json=data, params=params)

    def delete(self, record_id: str) -> None:
        self._client._delete(f"{self._base}/{record_id}")

    def create_many(self, records: list[dict]) -> list[T]:
        data = self._client._post(f"{self._base}/batch", json={"records": records})
        return data.get("records", data)

    def upsert_many(self, records: list[dict], upsert_by: list[str] | None = None) -> dict:
        payload: dict[str, Any] = {"records": records}
        if upsert_by: payload["upsert_by"] = upsert_by
        return self._client._post(f"{self._base}/batch-upsert", json=payload)

    def subscribe(self, callback: Callable[[dict], None], *, filter: str | None = None) -> Callable[[], None]:
        """
        SSE subscription using a background thread. Returns an unsubscribe callable.

        Note: requires ``httpx_sse`` package (``uv pip install httpx-sse`` or ``pip install httpx-sse``).
        """
        return self._client.realtime.subscribe(self._name, callback, filter=filter)


class AsyncCollectionClient(Generic[T]):
    """Asynchronous typed collection client."""

    def __init__(self, client: "AsyncFastCMS", name: str):
        self._client = client
        self._name = name

    @property
    def _base(self) -> str:
        return f"/api/v1/{self._name}/records"

    async def get_list(
        self,
        *,
        filter: str | None = None,
        sort: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        expand: str | None = None,
        fields: str | None = None,
        skip_total: bool = False,
    ) -> dict:
        params: dict[str, Any] = {}
        if filter:    params["filter"] = filter
        if sort:      params["sort"] = sort
        if page:      params["page"] = page
        if per_page:  params["per_page"] = per_page
        if expand:    params["expand"] = expand
        if fields:    params["fields"] = fields
        if skip_total: params["skip_total"] = "true"
        return await self._client._get(self._base, params=params)

    async def get_one(self, record_id: str, *, expand: str | None = None, fields: str | None = None) -> T:
        params: dict[str, Any] = {}
        if expand: params["expand"] = expand
        if fields: params["fields"] = fields
        return await self._client._get(f"{self._base}/{record_id}", params=params)

    async def create(self, data: dict, *, expand: str | None = None) -> T:
        params = {"expand": expand} if expand else {}
        return await self._client._post(self._base, json=data, params=params)

    async def update(self, record_id: str, data: dict, *, expand: str | None = None) -> T:
        params = {"expand": expand} if expand else {}
        return await self._client._patch(f"{self._base}/{record_id}", json=data, params=params)

    async def delete(self, record_id: str) -> None:
        await self._client._delete(f"{self._base}/{record_id}")

    async def create_many(self, records: list[dict]) -> list[T]:
        data = await self._client._post(f"{self._base}/batch", json={"records": records})
        return data.get("records", data)

    async def upsert_many(self, records: list[dict], upsert_by: list[str] | None = None) -> dict:
        payload: dict[str, Any] = {"records": records}
        if upsert_by: payload["upsert_by"] = upsert_by
        return await self._client._post(f"{self._base}/batch-upsert", json=payload)
