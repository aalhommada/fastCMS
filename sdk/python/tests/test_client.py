"""
Tests for FastCMS Python SDK — sync and async clients.
Uses respx to mock httpx requests.
"""
import pytest
import respx
import httpx

from fastcms import FastCMS, AsyncFastCMS, AuthError, ValidationError, NotFoundError, FastCMSError


BASE = "http://localhost:8000"


# ─── Sync client tests ────────────────────────────────────────────────────────

class TestFastCMSSync:

    @respx.mock
    def test_sign_in_stores_tokens(self):
        respx.post(f"{BASE}/api/v1/auth/login").mock(return_value=httpx.Response(200, json={
            "access_token": "acc123",
            "refresh_token": "ref456",
            "user": {"id": "u1", "email": "a@b.com"},
        }))

        cms = FastCMS(BASE)
        result = cms.auth.sign_in("a@b.com", "password")

        assert result["access_token"] == "acc123"
        assert cms._tokens["access_token"] == "acc123"

    @respx.mock
    def test_collection_get_list(self):
        respx.get(f"{BASE}/api/v1/posts/records").mock(return_value=httpx.Response(200, json={
            "items": [{"id": "1", "title": "Hello"}],
            "total": 1,
            "page": 1,
            "per_page": 30,
            "total_pages": 1,
        }))

        cms = FastCMS(BASE)
        result = cms.collection("posts").get_list()

        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "Hello"

    @respx.mock
    def test_collection_create(self):
        respx.post(f"{BASE}/api/v1/posts/records").mock(return_value=httpx.Response(201, json={
            "id": "abc", "title": "New Post",
        }))

        cms = FastCMS(BASE)
        record = cms.collection("posts").create({"title": "New Post"})

        assert record["id"] == "abc"

    @respx.mock
    def test_collection_update(self):
        respx.patch(f"{BASE}/api/v1/posts/records/abc").mock(return_value=httpx.Response(200, json={
            "id": "abc", "title": "Updated",
        }))

        cms = FastCMS(BASE)
        record = cms.collection("posts").update("abc", {"title": "Updated"})
        assert record["title"] == "Updated"

    @respx.mock
    def test_collection_delete(self):
        respx.delete(f"{BASE}/api/v1/posts/records/abc").mock(return_value=httpx.Response(204))

        cms = FastCMS(BASE)
        cms.collection("posts").delete("abc")  # Should not raise

    @respx.mock
    def test_auth_error_on_401(self):
        respx.get(f"{BASE}/api/v1/auth/me").mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))

        cms = FastCMS(BASE)
        with pytest.raises(AuthError) as exc_info:
            cms.auth.me()
        assert exc_info.value.status == 401

    @respx.mock
    def test_validation_error_on_422(self):
        respx.post(f"{BASE}/api/v1/auth/register").mock(return_value=httpx.Response(422, json={
            "detail": "Validation error",
            "errors": {"email": ["Invalid email"]},
        }))

        cms = FastCMS(BASE)
        with pytest.raises(ValidationError) as exc_info:
            cms.auth.sign_up("bad-email", "pass")
        assert exc_info.value.fields == {"email": ["Invalid email"]}

    @respx.mock
    def test_not_found_error_on_404(self):
        respx.get(f"{BASE}/api/v1/posts/records/999").mock(return_value=httpx.Response(404, json={"detail": "Not found"}))

        cms = FastCMS(BASE)
        with pytest.raises(NotFoundError):
            cms.collection("posts").get_one("999")

    @respx.mock
    def test_api_key_header(self):
        route = respx.get(f"{BASE}/api/v1/posts/records").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))

        cms = FastCMS(BASE, api_key="my-key")
        cms.collection("posts").get_list()

        assert route.calls[0].request.headers.get("x-api-key") == "my-key"

    @respx.mock
    def test_bearer_token_header_after_sign_in(self):
        respx.post(f"{BASE}/api/v1/auth/login").mock(return_value=httpx.Response(200, json={
            "access_token": "tok",
            "refresh_token": "ref",
        }))
        route = respx.get(f"{BASE}/api/v1/auth/me").mock(return_value=httpx.Response(200, json={"id": "u1"}))

        cms = FastCMS(BASE)
        cms.auth.sign_in("a@b.com", "pw")
        cms.auth.me()

        assert route.calls[0].request.headers.get("authorization") == "Bearer tok"

    def test_sign_out_clears_tokens(self):
        cms = FastCMS(BASE)
        cms._tokens = {"access_token": "tok", "refresh_token": "ref"}
        cms.auth.sign_out()
        assert cms._tokens is None

    @respx.mock
    def test_download_url_no_request(self):
        cms = FastCMS(BASE)
        url = cms.files.download_url("file123", thumb="300x200", token="t")
        assert url == f"{BASE}/api/v1/files/file123/download?thumb=300x200&token=t"


# ─── Async client tests ───────────────────────────────────────────────────────

class TestAsyncFastCMS:

    @pytest.mark.asyncio
    @respx.mock
    async def test_sign_in_stores_tokens(self):
        respx.post(f"{BASE}/api/v1/auth/login").mock(return_value=httpx.Response(200, json={
            "access_token": "acc",
            "refresh_token": "ref",
            "user": {"id": "u1"},
        }))

        async with AsyncFastCMS(BASE) as cms:
            result = await cms.auth.sign_in("a@b.com", "pw")
            assert result["access_token"] == "acc"
            assert cms._tokens["access_token"] == "acc"

    @pytest.mark.asyncio
    @respx.mock
    async def test_collection_get_list(self):
        respx.get(f"{BASE}/api/v1/posts/records").mock(return_value=httpx.Response(200, json={
            "items": [{"id": "1", "title": "Async Post"}],
            "total": 1,
        }))

        async with AsyncFastCMS(BASE) as cms:
            result = await cms.collection("posts").get_list()
            assert result["items"][0]["title"] == "Async Post"

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_error_on_401(self):
        respx.get(f"{BASE}/api/v1/auth/me").mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))

        async with AsyncFastCMS(BASE) as cms:
            with pytest.raises(AuthError):
                await cms.auth.me()

    @pytest.mark.asyncio
    async def test_download_url_no_request(self):
        async with AsyncFastCMS(BASE) as cms:
            url = cms.files.download_url("f1", thumb="100x100f")
            assert "thumb=100x100f" in url
