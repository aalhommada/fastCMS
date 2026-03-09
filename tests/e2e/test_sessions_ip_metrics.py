"""
E2E tests for session management, IP rules, and metrics endpoints.

Tests cover:
- GET  /api/v1/auth/sessions           — list active sessions
- DELETE /api/v1/auth/sessions/{id}    — revoke a session
- POST /api/v1/auth/logout-all         — logout all devices
- GET  /api/v1/admin/ip-rules          — list IP rules (admin)
- POST /api/v1/admin/ip-rules          — create IP rule (admin)
- DELETE /api/v1/admin/ip-rules/{id}   — delete IP rule (admin)
- GET  /api/v1/admin/metrics           — metrics JSON (admin)
- Admin UI pages accessible            — /admin/sessions, /admin/ip-rules, /admin/metrics
"""

import pytest
import bcrypt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User as UserModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(db: AsyncSession, email: str, role: str = "user") -> None:
    pw_hash = bcrypt.hashpw("TestPass1!".encode(), bcrypt.gensalt()).decode()
    user = UserModel(email=email, password_hash=pw_hash, role=role, verified=True)
    db.add(user)
    await db.commit()


async def _login(client: AsyncClient, email: str, password: str = "TestPass1!") -> tuple[str, str]:
    """Returns (access_token, refresh_token)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    token_data = data.get("token", data)
    return token_data["access_token"], token_data.get("refresh_token", "")


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestSessionManagement:

    async def test_get_sessions_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/sessions")
        assert resp.status_code == 401

    async def test_get_sessions_returns_list(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "sessions_user@test.dev")
        access_token, _ = await _login(client, "sessions_user@test.dev")
        resp = await client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    async def test_get_sessions_after_login_has_entry(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "sessions_user2@test.dev")
        access_token, _ = await _login(client, "sessions_user2@test.dev")
        resp = await client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        # At least one session exists (the one we just created)
        assert len(resp.json()["sessions"]) >= 1

    async def test_revoke_session_requires_auth(self, client: AsyncClient):
        resp = await client.delete("/api/v1/auth/sessions/fake-id")
        assert resp.status_code == 401

    async def test_revoke_session_removes_it(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "sessions_revoke@test.dev")
        access_token, _ = await _login(client, "sessions_revoke@test.dev")

        # Get session list
        sessions_resp = await client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        sessions = sessions_resp.json()["sessions"]
        assert len(sessions) >= 1
        session_id = sessions[0]["id"]

        # Revoke it
        del_resp = await client.delete(
            f"/api/v1/auth/sessions/{session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert del_resp.status_code == 204

    async def test_revoke_nonexistent_session_returns_404(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "sessions_404@test.dev")
        access_token, _ = await _login(client, "sessions_404@test.dev")
        resp = await client.delete(
            "/api/v1/auth/sessions/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code in (404, 403)

    async def test_logout_all_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout-all")
        assert resp.status_code == 401

    async def test_logout_all_succeeds(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "logout_all@test.dev")
        access_token, _ = await _login(client, "logout_all@test.dev")
        resp = await client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# IP Rules
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestIPRules:

    async def test_list_ip_rules_requires_admin(self, client: AsyncClient, db: AsyncSession):
        await _create_user(db, "iprules_user@test.dev", role="user")
        access_token, _ = await _login(client, "iprules_user@test.dev")
        resp = await client.get(
            "/api/v1/admin/ip-rules",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 403

    async def test_list_ip_rules_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/ip-rules")
        assert resp.status_code == 401

    async def test_list_ip_rules_admin_ok(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "iprules_admin@test.dev", role="admin")
        access_token, _ = await _login(client, "iprules_admin@test.dev")
        resp = await client.get(
            "/api/v1/admin/ip-rules",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_create_ip_rule_block(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "iprules_create@test.dev", role="admin")
        access_token, _ = await _login(client, "iprules_create@test.dev")
        resp = await client.post(
            "/api/v1/admin/ip-rules",
            json={"cidr": "10.0.0.1", "rule_type": "block", "reason": "Test block"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["cidr"] == "10.0.0.1"
        assert data["rule_type"] == "block"

    async def test_create_ip_rule_allow(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "iprules_allow@test.dev", role="admin")
        access_token, _ = await _login(client, "iprules_allow@test.dev")
        resp = await client.post(
            "/api/v1/admin/ip-rules",
            json={"cidr": "192.168.0.0/24", "rule_type": "allow"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["rule_type"] == "allow"

    async def test_create_ip_rule_invalid_cidr(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "iprules_bad@test.dev", role="admin")
        access_token, _ = await _login(client, "iprules_bad@test.dev")
        resp = await client.post(
            "/api/v1/admin/ip-rules",
            json={"cidr": "not-an-ip", "rule_type": "block"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code in (400, 422)

    async def test_delete_ip_rule(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "iprules_del@test.dev", role="admin")
        access_token, _ = await _login(client, "iprules_del@test.dev")
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create then delete
        create_resp = await client.post(
            "/api/v1/admin/ip-rules",
            json={"cidr": "1.2.3.4", "rule_type": "block"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/admin/ip-rules/{rule_id}",
            headers=headers,
        )
        assert del_resp.status_code == 204

    async def test_filter_ip_rules_by_type(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "iprules_filter@test.dev", role="admin")
        access_token, _ = await _login(client, "iprules_filter@test.dev")
        headers = {"Authorization": f"Bearer {access_token}"}

        await client.post("/api/v1/admin/ip-rules",
            json={"cidr": "5.5.5.5", "rule_type": "block"}, headers=headers)
        await client.post("/api/v1/admin/ip-rules",
            json={"cidr": "6.6.6.6", "rule_type": "allow"}, headers=headers)

        resp = await client.get(
            "/api/v1/admin/ip-rules?rule_type=block", headers=headers
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(r["rule_type"] == "block" for r in items)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestMetrics:

    async def test_metrics_requires_admin(self, client: AsyncClient, db: AsyncSession):
        await _create_user(db, "metrics_user@test.dev", role="user")
        access_token, _ = await _login(client, "metrics_user@test.dev")
        resp = await client.get(
            "/api/v1/admin/metrics",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 403

    async def test_metrics_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/metrics")
        assert resp.status_code == 401

    async def test_metrics_returns_snapshot(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "metrics_admin@test.dev", role="admin")
        access_token, _ = await _login(client, "metrics_admin@test.dev")
        resp = await client.get(
            "/api/v1/admin/metrics",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data
        assert "histograms" in data
        assert "gauges" in data

    async def test_metrics_has_request_counter(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "metrics_admin2@test.dev", role="admin")
        access_token, _ = await _login(client, "metrics_admin2@test.dev")
        headers = {"Authorization": f"Bearer {access_token}"}

        # Make a few requests so the counter is non-zero
        await client.get("/health")
        await client.get("/health")

        resp = await client.get("/api/v1/admin/metrics", headers=headers)
        assert resp.status_code == 200
        counters = resp.json()["counters"]
        # At least one key should reference http_requests
        assert any("http_requests" in k for k in counters)

    async def test_prometheus_endpoint(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_user(db, "metrics_prom@test.dev", role="admin")
        access_token, _ = await _login(client, "metrics_prom@test.dev")
        resp = await client.get(
            "/api/v1/admin/metrics/prometheus",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        # Prometheus text format starts with # HELP or a metric line
        assert "fastcms" in resp.text or "#" in resp.text


# ---------------------------------------------------------------------------
# Admin UI pages accessible
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestAdminUIPages:

    async def test_sessions_page_redirects_non_admin(self, client: AsyncClient):
        # httpx follows redirects by default; use a one-off request that doesn't
        resp = await client.request("GET", "/admin/sessions", follow_redirects=False)
        assert resp.status_code in (302, 303)

    async def test_ip_rules_page_redirects_non_admin(self, client: AsyncClient):
        resp = await client.request("GET", "/admin/ip-rules", follow_redirects=False)
        assert resp.status_code in (302, 303)

    async def test_metrics_page_redirects_non_admin(self, client: AsyncClient):
        resp = await client.request("GET", "/admin/metrics", follow_redirects=False)
        assert resp.status_code in (302, 303)

    async def test_sessions_template_exists(self):
        from pathlib import Path
        assert Path("app/admin/templates/sessions.html").exists()

    async def test_ip_rules_template_exists(self):
        from pathlib import Path
        assert Path("app/admin/templates/ip_rules.html").exists()

    async def test_metrics_template_exists(self):
        from pathlib import Path
        assert Path("app/admin/templates/metrics.html").exists()

    async def test_nav_links_in_base_template(self):
        from pathlib import Path
        base = Path("app/admin/templates/base.html").read_text()
        assert "/admin/sessions" in base
        assert "/admin/ip-rules" in base
        assert "/admin/metrics" in base
        assert "fa-desktop" in base
        assert "fa-shield-alt" in base
        assert "fa-tachometer-alt" in base
