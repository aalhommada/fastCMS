"""
Unit tests for webhook delivery improvements:
- Exponential backoff
- Delivery logging
- HMAC-SHA256 signature format
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.webhook_service import WebhookService, BACKOFF_BASE, BACKOFF_MAX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_webhook(**overrides):
    """Create a mock Webhook object."""
    w = MagicMock()
    w.id = overrides.get("id", "wh-123")
    w.url = overrides.get("url", "https://example.com/hook")
    w.collection_name = overrides.get("collection_name", "posts")
    w.events = overrides.get("events", "create,update")
    w.active = overrides.get("active", True)
    w.secret = overrides.get("secret", None)
    w.retry_count = overrides.get("retry_count", 3)
    w.last_triggered_at = overrides.get("last_triggered_at", None)
    return w


def _make_mock_response(status_code=200, text="OK"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Signature tests
# ---------------------------------------------------------------------------

class TestSignatureFormat:
    """Tests for HMAC-SHA256 signature generation."""

    def test_generate_signature(self):
        sig = WebhookService._generate_signature("hello", "secret")
        expected = hmac.new(b"secret", b"hello", hashlib.sha256).hexdigest()
        assert sig == expected

    def test_signature_is_hex(self):
        sig = WebhookService._generate_signature('{"data": 1}', "key")
        assert all(c in "0123456789abcdef" for c in sig)
        assert len(sig) == 64  # SHA256 hex digest

    def test_different_secrets_different_sigs(self):
        payload = '{"event": "test"}'
        sig1 = WebhookService._generate_signature(payload, "secret1")
        sig2 = WebhookService._generate_signature(payload, "secret2")
        assert sig1 != sig2


# ---------------------------------------------------------------------------
# Exponential backoff tests
# ---------------------------------------------------------------------------

class TestExponentialBackoff:
    """Tests for retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_no_retry_on_2xx(self):
        """Successful delivery should not retry."""
        webhook = _make_webhook(retry_count=3, secret=None)
        mock_resp = _make_mock_response(200)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "create", "rec-1", {"title": "Test"})

            # Should only call post once (no retries on success)
            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_5xx(self):
        """5xx errors should trigger retries."""
        webhook = _make_webhook(retry_count=2, secret=None)
        mock_resp_500 = _make_mock_response(500, "Internal Server Error")

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp_500)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await service._deliver_webhook(webhook, "create", "rec-1", {})

                # retry_count=2 means 3 total attempts (1 initial + 2 retries)
                assert mock_client.post.call_count == 3
                # Sleep called twice (before retry 1 and retry 2)
                assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_backoff_delays(self):
        """Backoff delays should increase exponentially."""
        webhook = _make_webhook(retry_count=3, secret=None)
        mock_resp_500 = _make_mock_response(500)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp_500)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await service._deliver_webhook(webhook, "create", "rec-1", {})

                delays = [call.args[0] for call in mock_sleep.call_args_list]
                # 1s, 2s, 4s (BACKOFF_BASE * 2^(attempt-1))
                assert delays == [1, 2, 4]

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        """4xx errors should not retry (client errors are permanent)."""
        webhook = _make_webhook(retry_count=3, secret=None)
        mock_resp = _make_mock_response(404, "Not Found")

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "create", "rec-1", {})

            # 4xx is < 500, so it's treated as success (no retry)
            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Connection errors should trigger retries."""
        webhook = _make_webhook(retry_count=1, secret=None)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await service._deliver_webhook(webhook, "create", "rec-1", {})

                # 1 initial + 1 retry = 2 total
                assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_backoff_max_cap(self):
        """Backoff delay should be capped at BACKOFF_MAX."""
        webhook = _make_webhook(retry_count=10, secret=None)
        mock_resp = _make_mock_response(500)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await service._deliver_webhook(webhook, "create", "rec-1", {})

                delays = [call.args[0] for call in mock_sleep.call_args_list]
                # All delays should be <= BACKOFF_MAX
                assert all(d <= BACKOFF_MAX for d in delays)
                # Last few should be capped at BACKOFF_MAX
                assert delays[-1] == BACKOFF_MAX


# ---------------------------------------------------------------------------
# Delivery logging tests
# ---------------------------------------------------------------------------

class TestDeliveryLogging:
    """Tests for webhook delivery log creation."""

    @pytest.mark.asyncio
    async def test_delivery_logged_on_success(self):
        """Successful delivery should create a log entry."""
        webhook = _make_webhook(retry_count=0, secret=None)
        mock_resp = _make_mock_response(200, "OK")

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "create", "rec-1", {"title": "Test"})

            # A delivery log should have been created
            service.delivery_repo.create.assert_called_once()
            delivery = service.delivery_repo.create.call_args[0][0]
            assert delivery.webhook_id == "wh-123"
            assert delivery.event_type == "create"
            assert delivery.record_id == "rec-1"
            assert delivery.status_code == 200
            assert delivery.success is True
            assert delivery.attempt == 1
            assert delivery.error is None

    @pytest.mark.asyncio
    async def test_delivery_logged_on_failure(self):
        """Failed delivery should create log entries for each attempt."""
        webhook = _make_webhook(retry_count=1, secret=None)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await service._deliver_webhook(webhook, "update", "rec-2", {})

                # 2 attempts = 2 log entries
                assert service.delivery_repo.create.call_count == 2
                # First attempt
                d1 = service.delivery_repo.create.call_args_list[0][0][0]
                assert d1.attempt == 1
                assert d1.success is False
                assert "refused" in d1.error
                # Second attempt
                d2 = service.delivery_repo.create.call_args_list[1][0][0]
                assert d2.attempt == 2
                assert d2.success is False

    @pytest.mark.asyncio
    async def test_delivery_logs_duration(self):
        """Delivery log should include duration_ms."""
        webhook = _make_webhook(retry_count=0, secret=None)
        mock_resp = _make_mock_response(200)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "delete", "rec-3", {})

            delivery = service.delivery_repo.create.call_args[0][0]
            assert delivery.duration_ms is not None
            assert delivery.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_delivery_truncates_response_body(self):
        """Response body should be truncated to 500 chars."""
        webhook = _make_webhook(retry_count=0, secret=None)
        long_body = "x" * 1000
        mock_resp = _make_mock_response(200, long_body)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "create", "rec-1", {})

            delivery = service.delivery_repo.create.call_args[0][0]
            assert len(delivery.response_body) == 500


# ---------------------------------------------------------------------------
# Signature header tests
# ---------------------------------------------------------------------------

class TestSignatureHeader:
    """Tests for signature in delivery headers."""

    @pytest.mark.asyncio
    async def test_signature_header_present_with_secret(self):
        """Webhook with secret should include sha256= prefixed signature."""
        webhook = _make_webhook(retry_count=0, secret="my-secret")
        mock_resp = _make_mock_response(200)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "create", "rec-1", {"title": "Hello"})

            call_kwargs = mock_client.post.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "X-Webhook-Signature" in headers
            assert headers["X-Webhook-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_no_signature_without_secret(self):
        """Webhook without secret should not include signature header."""
        webhook = _make_webhook(retry_count=0, secret=None)
        mock_resp = _make_mock_response(200)

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "create", "rec-1", {})

            call_kwargs = mock_client.post.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "X-Webhook-Signature" not in headers

    @pytest.mark.asyncio
    async def test_signature_verifiable(self):
        """Sent signature should be verifiable by the receiver."""
        secret = "webhook-verify-test"
        webhook = _make_webhook(retry_count=0, secret=secret)
        mock_resp = _make_mock_response(200)

        captured_payload = None
        captured_sig = None

        async def capture_post(url, json=None, headers=None):
            nonlocal captured_payload, captured_sig
            captured_payload = json
            captured_sig = headers.get("X-Webhook-Signature", "")
            return mock_resp

        with patch("app.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=capture_post)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            db = AsyncMock()
            service = WebhookService(db)
            service.repo = AsyncMock()
            service.delivery_repo = AsyncMock()
            service.delivery_repo.create = AsyncMock()

            await service._deliver_webhook(webhook, "create", "rec-1", {"x": 1})

            # Receiver verification: compute HMAC of the JSON payload
            assert captured_sig.startswith("sha256=")
            sig_hex = captured_sig[len("sha256="):]
            expected = hmac.new(
                secret.encode(),
                json.dumps(captured_payload).encode(),
                hashlib.sha256,
            ).hexdigest()
            assert sig_hex == expected


# ---------------------------------------------------------------------------
# Event filtering tests
# ---------------------------------------------------------------------------

class TestEventFiltering:
    """Tests for webhook event type filtering."""

    @pytest.mark.asyncio
    async def test_delivers_matching_event(self):
        webhook = _make_webhook(events="create,update")

        db = AsyncMock()
        service = WebhookService(db)
        service.repo = AsyncMock()
        service.repo.get_by_collection = AsyncMock(return_value=[webhook])
        service._deliver_webhook = AsyncMock()

        await service.deliver_event("posts", "create", "rec-1", {})
        service._deliver_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_non_matching_event(self):
        webhook = _make_webhook(events="create")

        db = AsyncMock()
        service = WebhookService(db)
        service.repo = AsyncMock()
        service.repo.get_by_collection = AsyncMock(return_value=[webhook])
        service._deliver_webhook = AsyncMock()

        await service.deliver_event("posts", "delete", "rec-1", {})
        service._deliver_webhook.assert_not_called()

    @pytest.mark.asyncio
    async def test_wildcard_matches_all_events(self):
        webhook = _make_webhook(events="*")

        db = AsyncMock()
        service = WebhookService(db)
        service.repo = AsyncMock()
        service.repo.get_by_collection = AsyncMock(return_value=[webhook])
        service._deliver_webhook = AsyncMock()

        await service.deliver_event("posts", "delete", "rec-1", {})
        service._deliver_webhook.assert_called_once()
