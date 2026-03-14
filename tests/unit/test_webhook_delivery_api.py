"""
Unit tests for webhook delivery API endpoints.

Tests the delivery log endpoints with a real DB (SQLite in-memory).
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.webhook import Webhook
from app.db.models.webhook_delivery import WebhookDelivery
from app.db.models.base import generate_uuid, utcnow


# ---------------------------------------------------------------------------
# Setup: In-memory SQLite + FastAPI test app
# ---------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


# Mock auth dependency
def mock_auth():
    ctx = MagicMock()
    ctx.user_id = "test-user"
    ctx.role = "admin"
    return ctx


# Create test app
test_app = FastAPI()

from app.api.v1.webhooks import router
from app.db.session import get_db
from app.core.dependencies import require_auth_context
from app.core.exceptions import NotFoundException
from fastapi import Request
from fastapi.responses import JSONResponse


@test_app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


test_app.include_router(router, prefix="/api/v1")
test_app.dependency_overrides[get_db] = override_get_db
test_app.dependency_overrides[require_auth_context] = mock_auth


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client():
    return TestClient(test_app)


@pytest.fixture
async def webhook_with_deliveries():
    """Create a webhook and some delivery logs."""
    async with TestSessionLocal() as db:
        # Create webhook
        wh = Webhook(
            id="wh-test-1",
            url="https://example.com/hook",
            collection_name="posts",
            events="create,update",
            active=True,
            secret="test-secret",
            retry_count=3,
        )
        db.add(wh)

        # Create delivery logs
        for i in range(5):
            d = WebhookDelivery(
                id=f"del-{i}",
                webhook_id="wh-test-1",
                event_type="create",
                record_id=f"rec-{i}",
                url="https://example.com/hook",
                status_code=200 if i < 3 else 500,
                response_body="OK" if i < 3 else "Internal Server Error",
                attempt=1,
                success=i < 3,
                duration_ms=100 + i * 10,
                error=None if i < 3 else "Server error",
            )
            db.add(d)

        await db.commit()
    return "wh-test-1"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeliveryEndpoints:
    """Tests for webhook delivery log API endpoints."""

    def test_list_deliveries_for_webhook(self, client, webhook_with_deliveries):
        resp = client.get("/api/v1/webhooks/wh-test-1/deliveries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5
        # All deliveries belong to this webhook
        assert all(d["webhook_id"] == "wh-test-1" for d in data["items"])

    def test_delivery_response_fields(self, client, webhook_with_deliveries):
        resp = client.get("/api/v1/webhooks/wh-test-1/deliveries?limit=1")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        # Check all expected fields are present
        assert "id" in item
        assert "webhook_id" in item
        assert "event_type" in item
        assert "record_id" in item
        assert "url" in item
        assert "status_code" in item
        assert "response_body" in item
        assert "attempt" in item
        assert "success" in item
        assert "duration_ms" in item
        assert "error" in item
        assert "created" in item

    def test_deliveries_pagination(self, client, webhook_with_deliveries):
        resp = client.get("/api/v1/webhooks/wh-test-1/deliveries?skip=0&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    def test_deliveries_for_nonexistent_webhook(self, client):
        resp = client.get("/api/v1/webhooks/nonexistent/deliveries")
        assert resp.status_code == 404

    def test_recent_deliveries(self, client, webhook_with_deliveries):
        resp = client.get("/api/v1/webhooks/deliveries/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    def test_recent_deliveries_empty(self, client):
        resp = client.get("/api/v1/webhooks/deliveries/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_deliveries_require_auth(self):
        """Without auth override, endpoints should require auth."""
        # Create a separate app without auth override
        no_auth_app = FastAPI()
        no_auth_app.include_router(router, prefix="/api/v1")
        no_auth_app.dependency_overrides[get_db] = override_get_db
        # Don't override require_auth_context

        no_auth_client = TestClient(no_auth_app, raise_server_exceptions=False)
        resp = no_auth_client.get("/api/v1/webhooks/deliveries/recent")
        assert resp.status_code in (401, 403, 500)  # depends on auth impl


class TestWebhookSignedColumn:
    """Tests that webhook responses include secret field for signed status."""

    def test_webhook_with_secret_shows_in_response(self, client, webhook_with_deliveries):
        resp = client.get("/api/v1/webhooks/wh-test-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["secret"] == "test-secret"

    async def test_webhook_without_secret(self, client):
        async with TestSessionLocal() as db:
            wh = Webhook(
                id="wh-no-secret",
                url="https://example.com/unsigned",
                collection_name="posts",
                events="create",
                active=True,
                secret=None,
                retry_count=0,
            )
            db.add(wh)
            await db.commit()

        resp = client.get("/api/v1/webhooks/wh-no-secret")
        assert resp.status_code == 200
        data = resp.json()
        assert data["secret"] is None
