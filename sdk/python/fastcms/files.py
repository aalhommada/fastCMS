"""
Files service — upload, list, download URL, protect, delete.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from .client import FastCMS, AsyncFastCMS


class FilesService:
    """Sync files service."""

    def __init__(self, client: "FastCMS"):
        self._client = client

    def upload(
        self,
        file: bytes | BinaryIO | Path,
        filename: str | None = None,
        *,
        collection_name: str | None = None,
        record_id: str | None = None,
        field_name: str | None = None,
    ) -> dict:
        """Upload a file. Returns the FileRecord dict."""
        if isinstance(file, Path):
            filename = filename or file.name
            file_bytes = file.read_bytes()
        elif isinstance(file, bytes):
            file_bytes = file
        else:
            file_bytes = file.read()

        fields: dict = {"file": (filename or "upload", file_bytes)}
        if collection_name: fields["collection_name"] = (None, collection_name)
        if record_id:       fields["record_id"] = (None, record_id)
        if field_name:      fields["field_name"] = (None, field_name)

        return self._client._request("POST", "/api/v1/files", files=fields)

    def list(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        collection_name: str | None = None,
        record_id: str | None = None,
    ) -> dict:
        params = {}
        if page:            params["page"] = page
        if per_page:        params["per_page"] = per_page
        if collection_name: params["collection_name"] = collection_name
        if record_id:       params["record_id"] = record_id
        return self._client._get("/api/v1/files", params=params)

    def get_one(self, file_id: str) -> dict:
        return self._client._get(f"/api/v1/files/{file_id}")

    def download_url(self, file_id: str, *, thumb: str | None = None, token: str | None = None) -> str:
        """Build the download URL for a file (no HTTP request made)."""
        base = self._client.base_url.rstrip("/")
        url = f"{base}/api/v1/files/{file_id}/download"
        params = []
        if thumb: params.append(f"thumb={thumb}")
        if token: params.append(f"token={token}")
        if params: url += "?" + "&".join(params)
        return url

    def get_token(self, file_id: str) -> dict:
        """Generate a short-lived download token for a protected file."""
        return self._client._post(f"/api/v1/files/{file_id}/token")

    def set_protected(self, file_id: str, protected: bool) -> dict:
        return self._client._request(
            "PATCH",
            f"/api/v1/files/{file_id}/protected",
            params={"protected": str(protected).lower()},
        )

    def delete(self, file_id: str) -> None:
        self._client._delete(f"/api/v1/files/{file_id}")


class AsyncFilesService:
    """Async files service (all methods are coroutines)."""

    def __init__(self, client: "AsyncFastCMS"):
        self._client = client

    async def upload(
        self,
        file: bytes | BinaryIO | Path,
        filename: str | None = None,
        *,
        collection_name: str | None = None,
        record_id: str | None = None,
        field_name: str | None = None,
    ) -> dict:
        if isinstance(file, Path):
            filename = filename or file.name
            file_bytes = file.read_bytes()
        elif isinstance(file, bytes):
            file_bytes = file
        else:
            file_bytes = file.read()

        fields: dict = {"file": (filename or "upload", file_bytes)}
        if collection_name: fields["collection_name"] = (None, collection_name)
        if record_id:       fields["record_id"] = (None, record_id)
        if field_name:      fields["field_name"] = (None, field_name)

        return await self._client._request("POST", "/api/v1/files", files=fields)

    async def list(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        collection_name: str | None = None,
        record_id: str | None = None,
    ) -> dict:
        params = {}
        if page:            params["page"] = page
        if per_page:        params["per_page"] = per_page
        if collection_name: params["collection_name"] = collection_name
        if record_id:       params["record_id"] = record_id
        return await self._client._get("/api/v1/files", params=params)

    async def get_one(self, file_id: str) -> dict:
        return await self._client._get(f"/api/v1/files/{file_id}")

    def download_url(self, file_id: str, *, thumb: str | None = None, token: str | None = None) -> str:
        base = self._client.base_url.rstrip("/")
        url = f"{base}/api/v1/files/{file_id}/download"
        params = []
        if thumb: params.append(f"thumb={thumb}")
        if token: params.append(f"token={token}")
        if params: url += "?" + "&".join(params)
        return url

    async def get_token(self, file_id: str) -> dict:
        return await self._client._post(f"/api/v1/files/{file_id}/token")

    async def set_protected(self, file_id: str, protected: bool) -> dict:
        return await self._client._request(
            "PATCH",
            f"/api/v1/files/{file_id}/protected",
            params={"protected": str(protected).lower()},
        )

    async def delete(self, file_id: str) -> None:
        await self._client._delete(f"/api/v1/files/{file_id}")
