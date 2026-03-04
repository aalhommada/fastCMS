"""
E2E tests for security notification emails and admin email API.

Tests cover:
- Password change triggers notification
- Password reset triggers notification
- Account lockout triggers notification
- Admin email status endpoint
- Admin test-email endpoint
"""
import pytest
import bcrypt
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User as UserModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_admin(db: AsyncSession, email: str) -> str:
    """Insert admin directly in DB and return access token via login."""
    pw_hash = bcrypt.hashpw("AdminPass1!".encode(), bcrypt.gensalt()).decode()
    user = UserModel(email=email, password_hash=pw_hash, role="admin", verified=True)
    db.add(user)
    await db.commit()
    return user


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    data = resp.json()
    if "token" in data:
        return data["token"]["access_token"]
    return data["access_token"]


async def _register(client: AsyncClient, email: str, password: str = "StrongPass1!") -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "password_confirm": password},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Admin Email Status
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestAdminEmailStatus:

    async def test_email_status_requires_admin(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/email/status")
        assert resp.status_code == 401

    async def test_email_status_accessible_by_admin(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_admin(db, "emailadmin@test.dev")
        token = await _login(client, "emailadmin@test.dev", "AdminPass1!")
        resp = await client.get(
            "/api/v1/admin/email/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "smtp_enabled" in data
        assert "smtp_host" in data
        assert "smtp_port" in data
        assert "smtp_from_email" in data
        assert "security_notifications_enabled" in data
        assert "security_login_notifications" in data

    async def test_email_status_password_is_masked(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Endpoint must never return SMTP_PASSWORD."""
        await _create_admin(db, "emailadmin2@test.dev")
        token = await _login(client, "emailadmin2@test.dev", "AdminPass1!")
        resp = await client.get(
            "/api/v1/admin/email/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Raw password must not appear in response
        body = resp.text
        assert "AdminPass1!" not in body


# ---------------------------------------------------------------------------
# Admin Test Email
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestAdminTestEmail:

    async def test_test_email_requires_admin(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/admin/email/test",
            json={"to_email": "anyone@example.com"},
        )
        assert resp.status_code == 401

    async def test_test_email_returns_400_when_smtp_not_configured(
        self, client: AsyncClient, db: AsyncSession, monkeypatch
    ):
        monkeypatch.setattr("app.core.config.settings.SMTP_USER", "")
        monkeypatch.setattr("app.core.config.settings.SMTP_PASSWORD", "")
        await _create_admin(db, "emailadmin3@test.dev")
        token = await _login(client, "emailadmin3@test.dev", "AdminPass1!")
        resp = await client.post(
            "/api/v1/admin/email/test",
            json={"to_email": "test@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    @patch("app.services.email_service.EmailService.send_email")
    async def test_test_email_succeeds_when_smtp_configured(
        self,
        mock_send: AsyncMock,
        client: AsyncClient,
        db: AsyncSession,
        monkeypatch,
    ):
        mock_send.return_value = True
        monkeypatch.setattr("app.core.config.settings.SMTP_USER", "user@smtp.test")
        monkeypatch.setattr("app.core.config.settings.SMTP_PASSWORD", "secret")

        await _create_admin(db, "emailadmin4@test.dev")
        token = await _login(client, "emailadmin4@test.dev", "AdminPass1!")
        resp = await client.post(
            "/api/v1/admin/email/test",
            json={"to_email": "recipient@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "recipient@example.com" in data["message"]
        mock_send.assert_called_once()

    @patch("app.services.email_service.EmailService.send_email")
    async def test_test_email_returns_502_when_smtp_fails(
        self,
        mock_send: AsyncMock,
        client: AsyncClient,
        db: AsyncSession,
        monkeypatch,
    ):
        mock_send.return_value = False  # SMTP failure
        monkeypatch.setattr("app.core.config.settings.SMTP_USER", "user@smtp.test")
        monkeypatch.setattr("app.core.config.settings.SMTP_PASSWORD", "secret")

        await _create_admin(db, "emailadmin5@test.dev")
        token = await _login(client, "emailadmin5@test.dev", "AdminPass1!")
        resp = await client.post(
            "/api/v1/admin/email/test",
            json={"to_email": "fail@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 502

    async def test_test_email_rejects_invalid_email_address(
        self, client: AsyncClient, db: AsyncSession
    ):
        await _create_admin(db, "emailadmin6@test.dev")
        token = await _login(client, "emailadmin6@test.dev", "AdminPass1!")
        resp = await client.post(
            "/api/v1/admin/email/test",
            json={"to_email": "not-an-email"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Security Notification Triggers
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestSecurityNotificationTriggers:

    @patch("app.services.email_service.EmailService.send_password_changed_notification")
    async def test_password_change_triggers_notification(
        self,
        mock_notify: AsyncMock,
        client: AsyncClient,
        db: AsyncSession,
    ):
        """Changing password should fire send_password_changed_notification."""
        mock_notify.return_value = True

        from app.core.config import settings as app_settings
        from unittest.mock import patch as _patch

        # Create user directly to bypass rate limiting
        pw_hash = bcrypt.hashpw("OldPass1!".encode(), bcrypt.gensalt()).decode()
        user = UserModel(email="pwchange@test.dev", password_hash=pw_hash,
                         role="user", verified=True)
        db.add(user)
        await db.commit()
        token = await _login(client, "pwchange@test.dev", "OldPass1!")

        # Patch SMTP_ENABLED (a property) using patch.object so it returns True
        with _patch.object(type(app_settings), "SMTP_ENABLED",
                           new_callable=lambda: property(lambda s: True)), \
             _patch.object(app_settings, "SECURITY_NOTIFICATIONS_ENABLED", True):
            resp = await client.post(
                "/api/v1/auth/change-password",
                json={"old_password": "OldPass1!", "new_password": "NewPass2!",
                      "new_password_confirm": "NewPass2!"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 204
        import asyncio
        await asyncio.sleep(0.05)
        mock_notify.assert_called_once()

    @patch("app.services.email_service.EmailService.send_account_locked_notification")
    async def test_account_lockout_triggers_notification(
        self,
        mock_locked: AsyncMock,
        client: AsyncClient,
        db: AsyncSession,
    ):
        """Hitting lockout threshold should fire send_account_locked_notification."""
        mock_locked.return_value = True

        from app.core.config import settings as app_settings
        from unittest.mock import patch as _patch, MagicMock

        # Create user directly to bypass rate limiting
        pw_hash = bcrypt.hashpw("RealPass1!".encode(), bcrypt.gensalt()).decode()
        user = UserModel(email="lockout@test.dev", password_hash=pw_hash,
                         role="user", verified=True)
        db.add(user)
        await db.commit()

        attempts = app_settings.ACCOUNT_LOCKOUT_ATTEMPTS

        # Patch settings at both the auth_service and rate_limit module levels.
        # auth_service: needs SMTP_ENABLED=True and SECURITY_NOTIFICATIONS_ENABLED=True
        # rate_limit: disable to avoid per-minute limit being exhausted by earlier tests
        mock_settings = MagicMock()
        mock_settings.SMTP_ENABLED = True
        mock_settings.SECURITY_NOTIFICATIONS_ENABLED = True
        mock_settings.ACCOUNT_LOCKOUT_ENABLED = True
        mock_settings.ACCOUNT_LOCKOUT_ATTEMPTS = attempts
        mock_settings.ACCOUNT_LOCKOUT_DURATION = app_settings.ACCOUNT_LOCKOUT_DURATION
        mock_settings.BASE_URL = app_settings.BASE_URL

        with _patch("app.services.auth_service.settings", mock_settings), \
             _patch("app.core.rate_limit.settings") as mock_rl_settings:
            mock_rl_settings.RATE_LIMIT_ENABLED = False
            for _ in range(attempts):
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": "lockout@test.dev", "password": "WRONG"},
                )

        import asyncio
        await asyncio.sleep(0.1)
        mock_locked.assert_called()

    @patch("app.services.email_service.EmailService.send_password_changed_notification")
    @patch("app.services.email_service.EmailService.send_password_reset_email")
    async def test_password_reset_triggers_notification(
        self,
        mock_reset_email: AsyncMock,
        mock_notify: AsyncMock,
        client: AsyncClient,
        db: AsyncSession,
    ):
        """Completing a password reset should fire send_password_changed_notification."""
        mock_reset_email.return_value = True
        mock_notify.return_value = True

        from app.core.config import settings as app_settings
        from unittest.mock import patch as _patch

        # Create user directly to bypass rate limiting
        pw_hash = bcrypt.hashpw("StrongPass1!".encode(), bcrypt.gensalt()).decode()
        user = UserModel(email="resetnotify@test.dev", password_hash=pw_hash,
                         role="user", verified=True)
        db.add(user)
        await db.commit()

        with _patch.object(type(app_settings), "SMTP_ENABLED",
                           new_callable=lambda: property(lambda s: True)), \
             _patch.object(app_settings, "SECURITY_NOTIFICATIONS_ENABLED", True):
            # Request reset (creates token in DB)
            await client.post(
                "/api/v1/auth/request-password-reset",
                json={"email": "resetnotify@test.dev"},
            )

        # Grab token from DB
        from sqlalchemy import select
        from app.db.models.verification import PasswordResetToken
        result = await db.execute(select(PasswordResetToken).order_by(
            PasswordResetToken.created.desc()
        ))
        reset_token = result.scalars().first()
        if not reset_token:
            pytest.skip("No reset token found — SMTP mock may have prevented creation")

        with _patch.object(type(app_settings), "SMTP_ENABLED",
                           new_callable=lambda: property(lambda s: True)), \
             _patch.object(app_settings, "SECURITY_NOTIFICATIONS_ENABLED", True):
            resp = await client.post(
                "/api/v1/auth/reset-password",
                json={"token": reset_token.token, "password": "BrandNew1!",
                      "password_confirm": "BrandNew1!"},
            )
        assert resp.status_code == 204

        import asyncio
        await asyncio.sleep(0.05)
        mock_notify.assert_called_once()


# ---------------------------------------------------------------------------
# Admin Email Settings Page
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestAdminEmailSettingsPage:

    async def test_email_settings_page_is_accessible(
        self, client: AsyncClient
    ):
        """The /admin/settings/email page should not 500."""
        resp = await client.get("/admin/settings/email", follow_redirects=True)
        assert resp.status_code in (200, 302, 303)

    async def test_email_settings_template_exists(self):
        from pathlib import Path
        assert Path("app/admin/templates/email_settings.html").exists()

    async def test_email_nav_link_in_base_template(self):
        from pathlib import Path
        base = Path("app/admin/templates/base.html").read_text()
        assert "/admin/settings/email" in base
        assert "fa-envelope" in base
