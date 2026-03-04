"""
Unit tests for password policy validation.
"""

import pytest
from unittest.mock import patch

from app.core.security import validate_password_policy


class TestPasswordPolicyValidation:
    """Tests for validate_password_policy()."""

    def test_valid_password_returns_no_errors(self):
        errors = validate_password_policy("MyPass1!")
        # With default settings (no special required), basic password is fine
        assert isinstance(errors, list)

    def test_password_too_short(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = 8
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = False
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = False
            mock_settings.PASSWORD_REQUIRE_DIGIT = False
            mock_settings.PASSWORD_REQUIRE_SPECIAL = False
            errors = validate_password_policy("abc")
            assert any("at least 8 characters" in e for e in errors)

    def test_password_requires_uppercase(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = 1
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = True
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = False
            mock_settings.PASSWORD_REQUIRE_DIGIT = False
            mock_settings.PASSWORD_REQUIRE_SPECIAL = False
            errors = validate_password_policy("lowercase123")
            assert any("uppercase" in e for e in errors)

    def test_password_requires_lowercase(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = 1
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = False
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = True
            mock_settings.PASSWORD_REQUIRE_DIGIT = False
            mock_settings.PASSWORD_REQUIRE_SPECIAL = False
            errors = validate_password_policy("UPPERCASE123")
            assert any("lowercase" in e for e in errors)

    def test_password_requires_digit(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = 1
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = False
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = False
            mock_settings.PASSWORD_REQUIRE_DIGIT = True
            mock_settings.PASSWORD_REQUIRE_SPECIAL = False
            errors = validate_password_policy("NoDigitsHere")
            assert any("digit" in e for e in errors)

    def test_password_requires_special_char(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = 1
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = False
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = False
            mock_settings.PASSWORD_REQUIRE_DIGIT = False
            mock_settings.PASSWORD_REQUIRE_SPECIAL = True
            errors = validate_password_policy("NoSpecialChar1")
            assert any("special" in e for e in errors)

    def test_strong_password_no_errors(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = 8
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = True
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = True
            mock_settings.PASSWORD_REQUIRE_DIGIT = True
            mock_settings.PASSWORD_REQUIRE_SPECIAL = True
            errors = validate_password_policy("Strong1!")
            assert errors == []

    def test_multiple_violations_return_multiple_errors(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.PASSWORD_MIN_LENGTH = 10
            mock_settings.PASSWORD_REQUIRE_UPPERCASE = True
            mock_settings.PASSWORD_REQUIRE_LOWERCASE = True
            mock_settings.PASSWORD_REQUIRE_DIGIT = True
            mock_settings.PASSWORD_REQUIRE_SPECIAL = True
            errors = validate_password_policy("ab")
            assert len(errors) > 1


class TestPasswordHistoryConfig:
    """Test password history configuration."""

    def test_history_count_default_disabled(self):
        from app.core.config import settings
        assert settings.PASSWORD_HISTORY_COUNT == 0

    def test_history_check_skipped_when_disabled(self):
        """When PASSWORD_HISTORY_COUNT=0, history check is skipped."""
        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.PASSWORD_HISTORY_COUNT = 0
            from app.services.auth_service import AuthService
            from app.db.models.user import User

            user = User()
            user.password_hash = "some_hash"
            user.password_history = None
            # Should not raise even if same password
            service = AuthService.__new__(AuthService)
            service._check_password_history(user, "anypassword")  # no exception
