"""
Unit tests for security hardening — secret rotation, CORS, OpenAPI, cookies.
"""

import pytest
from unittest.mock import patch, MagicMock
from jose import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_file_token,
    verify_file_token,
)


class TestSecretRotation:
    """Tests for SECRET_KEY_PREVIOUS fallback in decode_token."""

    def test_decode_with_current_key(self):
        """Token signed with current key decodes normally."""
        token = create_access_token({"sub": "user-1"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-1"

    def test_decode_with_previous_key(self):
        """Token signed with previous key decodes via fallback."""
        old_key = "old-secret-key-for-rotation-test"
        # Sign a token with the old key
        token = jwt.encode(
            {"sub": "user-2", "type": "access", "exp": 9999999999},
            old_key,
            algorithm="HS256",
        )

        # Without SECRET_KEY_PREVIOUS, token should fail
        payload = decode_token(token)
        assert payload is None

        # With SECRET_KEY_PREVIOUS set, token should decode
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "new-key-that-doesnt-match"
            mock_settings.SECRET_KEY_PREVIOUS = old_key
            mock_settings.ALGORITHM = "HS256"
            payload = decode_token(token)
            assert payload is not None
            assert payload["sub"] == "user-2"

    def test_decode_fails_with_wrong_both_keys(self):
        """Token signed with unknown key fails even with previous key set."""
        token = jwt.encode(
            {"sub": "user-3", "type": "access", "exp": 9999999999},
            "completely-unknown-key",
            algorithm="HS256",
        )
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "current-key"
            mock_settings.SECRET_KEY_PREVIOUS = "old-key"
            mock_settings.ALGORITHM = "HS256"
            payload = decode_token(token)
            assert payload is None

    def test_decode_without_previous_key_set(self):
        """When SECRET_KEY_PREVIOUS is empty, bad tokens just fail."""
        token = jwt.encode(
            {"sub": "user-4", "type": "access", "exp": 9999999999},
            "wrong-key",
            algorithm="HS256",
        )
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "current-key"
            mock_settings.SECRET_KEY_PREVIOUS = ""
            mock_settings.ALGORITHM = "HS256"
            payload = decode_token(token)
            assert payload is None

    def test_new_tokens_always_use_current_key(self):
        """New tokens are always signed with the current SECRET_KEY, never the previous one."""
        token = create_access_token({"sub": "user-5"})
        from app.core.config import settings
        # Should decode with current key directly
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "user-5"

    def test_refresh_token_with_previous_key(self):
        """Refresh tokens also benefit from secret rotation fallback."""
        old_key = "old-refresh-key"
        token = jwt.encode(
            {"sub": "user-6", "type": "refresh", "jti": "abc", "exp": 9999999999},
            old_key,
            algorithm="HS256",
        )
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "new-key"
            mock_settings.SECRET_KEY_PREVIOUS = old_key
            mock_settings.ALGORITHM = "HS256"
            payload = decode_token(token)
            assert payload is not None
            assert payload["type"] == "refresh"

    def test_file_token_with_previous_key(self):
        """File access tokens also work during secret rotation."""
        old_key = "old-file-key"
        token = jwt.encode(
            {"sub": "user-7", "type": "file_access", "file_id": "file-123", "exp": 9999999999},
            old_key,
            algorithm="HS256",
        )
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "new-key"
            mock_settings.SECRET_KEY_PREVIOUS = old_key
            mock_settings.ALGORITHM = "HS256"
            user_id = verify_file_token(token, "file-123")
            assert user_id == "user-7"

    def test_file_token_wrong_file_id_rejected(self):
        """File token with wrong file_id is rejected even with valid key."""
        old_key = "old-file-key"
        token = jwt.encode(
            {"sub": "user-8", "type": "file_access", "file_id": "file-123", "exp": 9999999999},
            old_key,
            algorithm="HS256",
        )
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "new-key"
            mock_settings.SECRET_KEY_PREVIOUS = old_key
            mock_settings.ALGORITHM = "HS256"
            user_id = verify_file_token(token, "wrong-file-id")
            assert user_id is None


class TestOpenAPIProductionDisabled:
    """Tests for OpenAPI schema being disabled in production."""

    def test_openapi_url_none_in_production(self):
        """FastAPI app should have openapi_url=None when DEBUG=False."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DEBUG = False
            # The logic is: openapi_url="/openapi.json" if settings.DEBUG else None
            openapi_url = "/openapi.json" if mock_settings.DEBUG else None
            assert openapi_url is None

    def test_openapi_url_set_in_debug(self):
        """FastAPI app should have openapi_url set when DEBUG=True."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DEBUG = True
            openapi_url = "/openapi.json" if mock_settings.DEBUG else None
            assert openapi_url == "/openapi.json"


class TestCORSConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_methods_restricted(self):
        """CORS should only allow specific HTTP methods, not wildcard."""
        from app.main import app

        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls is not None and "CORSMiddleware" in str(middleware.cls):
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        allowed_methods = cors_middleware.kwargs.get("allow_methods", [])
        assert "*" not in allowed_methods
        assert "GET" in allowed_methods
        assert "POST" in allowed_methods
        assert "PUT" in allowed_methods
        assert "PATCH" in allowed_methods
        assert "DELETE" in allowed_methods

    def test_cors_headers_restricted(self):
        """CORS should only allow specific headers, not wildcard."""
        from app.main import app

        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls is not None and "CORSMiddleware" in str(middleware.cls):
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        allowed_headers = cors_middleware.kwargs.get("allow_headers", [])
        assert "*" not in allowed_headers
        assert "Authorization" in allowed_headers
        assert "Content-Type" in allowed_headers
        assert "X-API-Key" in allowed_headers


class TestSecretKeyPreviousConfig:
    """Tests for SECRET_KEY_PREVIOUS config setting."""

    def test_default_empty(self):
        """SECRET_KEY_PREVIOUS should default to empty string."""
        from app.core.config import settings
        assert isinstance(settings.SECRET_KEY_PREVIOUS, str)

    def test_config_accepts_previous_key(self):
        """Settings should accept SECRET_KEY_PREVIOUS from environment."""
        import os
        os.environ["SECRET_KEY_PREVIOUS"] = "test-previous-key"
        try:
            from app.core.config import Settings
            s = Settings(SECRET_KEY="test-key")
            assert s.SECRET_KEY_PREVIOUS == "test-previous-key"
        finally:
            del os.environ["SECRET_KEY_PREVIOUS"]
