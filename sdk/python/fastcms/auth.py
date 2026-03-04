"""
Authentication service — sync and async variants.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import FastCMS, AsyncFastCMS


class _AuthServiceBase:
    """Shared auth logic; subclasses provide _post / _get / _patch / _delete."""

    # -- helpers implemented by subclasses ----------------------------------
    def _post(self, path: str, **kw) -> Any: ...
    def _get(self, path: str, **kw) -> Any: ...
    def _patch(self, path: str, **kw) -> Any: ...
    def _delete(self, path: str, **kw) -> Any: ...
    def _set_tokens(self, data: dict) -> None: ...


class AuthService(_AuthServiceBase):
    """Sync authentication service."""

    def __init__(self, client: "FastCMS"):
        self._client = client

    def _post(self, path, **kw):
        return self._client._post(path, **kw)

    def _get(self, path, **kw):
        return self._client._get(path, **kw)

    def _patch(self, path, **kw):
        return self._client._patch(path, **kw)

    def _delete(self, path, **kw):
        return self._client._delete(path, **kw)

    def _set_tokens(self, data: dict):
        self._client._set_tokens(data)

    # -----------------------------------------------------------------------

    def sign_up(self, email: str, password: str, name: str | None = None) -> dict:
        """Register a new user. Returns the created user object."""
        return self._post("/api/v1/auth/register", json={"email": email, "password": password, "name": name})

    def sign_in(self, email: str, password: str) -> dict:
        """Sign in with email and password. Returns {user, tokens}."""
        data = self._post("/api/v1/auth/login", json={"email": email, "password": password})
        self._set_tokens(data)
        return data

    def sign_out(self) -> None:
        """Clear local authentication state."""
        self._client.clear_auth()

    def logout_all(self) -> None:
        """Revoke all sessions server-side, then clear local auth."""
        self._post("/api/v1/auth/logout-all")
        self._client.clear_auth()

    def refresh_token(self, refresh_token: str) -> dict:
        """Refresh the access token. Returns new tokens."""
        data = self._post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        self._set_tokens(data)
        return data

    def me(self) -> dict:
        """Get the current authenticated user."""
        return self._get("/api/v1/auth/me")

    def update_me(self, **fields) -> dict:
        """Update the current user's profile."""
        return self._patch("/api/v1/auth/me", json=fields)

    def request_password_reset(self, email: str) -> None:
        self._post("/api/v1/auth/request-password-reset", json={"email": email})

    def reset_password(self, token: str, new_password: str) -> None:
        self._post("/api/v1/auth/reset-password", json={"token": token, "new_password": new_password})

    def change_password(self, old_password: str, new_password: str) -> None:
        self._post("/api/v1/auth/change-password", json={"old_password": old_password, "new_password": new_password})

    def request_otp(self, email: str) -> None:
        """Send a one-time password to the email address."""
        self._post("/api/v1/auth/request-otp", json={"email": email})

    def auth_with_otp(self, email: str, code: str) -> dict:
        """Authenticate with an OTP code. Returns {user, tokens}."""
        data = self._post("/api/v1/auth/auth-with-otp", json={"email": email, "code": code})
        self._set_tokens(data)
        return data

    def request_email_change(self, new_email: str, current_password: str) -> None:
        self._post("/api/v1/auth/request-email-change", json={"new_email": new_email, "password": current_password})

    def confirm_email_change(self, token: str) -> None:
        self._post("/api/v1/auth/confirm-email-change", json={"token": token})

    def verify_email(self, token: str) -> None:
        self._post("/api/v1/auth/verify-email", json={"token": token})

    def get_sessions(self) -> list[dict]:
        return self._get("/api/v1/auth/sessions")["sessions"]

    def revoke_session(self, session_id: str) -> None:
        self._delete(f"/api/v1/auth/sessions/{session_id}")

    def oauth_url(self, provider: str) -> str:
        """Get the OAuth redirect URL for the given provider (google, github, microsoft)."""
        return self._get(f"/api/v1/oauth/login/{provider}")["auth_url"]


class AsyncAuthService(_AuthServiceBase):
    """Async authentication service (identical API, all methods are coroutines)."""

    def __init__(self, client: "AsyncFastCMS"):
        self._client = client

    async def _post(self, path, **kw):
        return await self._client._post(path, **kw)

    async def _get(self, path, **kw):
        return await self._client._get(path, **kw)

    async def _patch(self, path, **kw):
        return await self._client._patch(path, **kw)

    async def _delete(self, path, **kw):
        return await self._client._delete(path, **kw)

    def _set_tokens(self, data: dict):
        self._client._set_tokens(data)

    async def sign_up(self, email: str, password: str, name: str | None = None) -> dict:
        return await self._post("/api/v1/auth/register", json={"email": email, "password": password, "name": name})

    async def sign_in(self, email: str, password: str) -> dict:
        data = await self._post("/api/v1/auth/login", json={"email": email, "password": password})
        self._set_tokens(data)
        return data

    def sign_out(self) -> None:
        self._client.clear_auth()

    async def logout_all(self) -> None:
        await self._post("/api/v1/auth/logout-all")
        self._client.clear_auth()

    async def refresh_token(self, refresh_token: str) -> dict:
        data = await self._post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        self._set_tokens(data)
        return data

    async def me(self) -> dict:
        return await self._get("/api/v1/auth/me")

    async def update_me(self, **fields) -> dict:
        return await self._patch("/api/v1/auth/me", json=fields)

    async def request_password_reset(self, email: str) -> None:
        await self._post("/api/v1/auth/request-password-reset", json={"email": email})

    async def reset_password(self, token: str, new_password: str) -> None:
        await self._post("/api/v1/auth/reset-password", json={"token": token, "new_password": new_password})

    async def change_password(self, old_password: str, new_password: str) -> None:
        await self._post("/api/v1/auth/change-password", json={"old_password": old_password, "new_password": new_password})

    async def request_otp(self, email: str) -> None:
        await self._post("/api/v1/auth/request-otp", json={"email": email})

    async def auth_with_otp(self, email: str, code: str) -> dict:
        data = await self._post("/api/v1/auth/auth-with-otp", json={"email": email, "code": code})
        self._set_tokens(data)
        return data

    async def request_email_change(self, new_email: str, current_password: str) -> None:
        await self._post("/api/v1/auth/request-email-change", json={"new_email": new_email, "password": current_password})

    async def confirm_email_change(self, token: str) -> None:
        await self._post("/api/v1/auth/confirm-email-change", json={"token": token})

    async def verify_email(self, token: str) -> None:
        await self._post("/api/v1/auth/verify-email", json={"token": token})

    async def get_sessions(self) -> list[dict]:
        return (await self._get("/api/v1/auth/sessions"))["sessions"]

    async def revoke_session(self, session_id: str) -> None:
        await self._delete(f"/api/v1/auth/sessions/{session_id}")

    async def oauth_url(self, provider: str) -> str:
        return (await self._get(f"/api/v1/oauth/login/{provider}"))["auth_url"]
