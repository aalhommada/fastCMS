"""
Unit tests for account lockout functionality.
Tests that accounts lock after N failed attempts and unlock properly.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings


class TestAccountLockoutConfig:
    """Test lockout configuration defaults."""

    def test_lockout_enabled_by_default(self):
        assert settings.ACCOUNT_LOCKOUT_ENABLED is True

    def test_default_max_attempts(self):
        assert settings.ACCOUNT_LOCKOUT_ATTEMPTS == 5

    def test_default_lockout_duration(self):
        assert settings.ACCOUNT_LOCKOUT_DURATION == 1800  # 30 minutes


class TestUserModelLockoutFields:
    """Test that User model has lockout fields."""

    def test_user_has_failed_login_attempts_field(self):
        from app.db.models.user import User
        assert hasattr(User, "failed_login_attempts")

    def test_user_has_locked_until_field(self):
        from app.db.models.user import User
        assert hasattr(User, "locked_until")

    def test_user_has_password_history_field(self):
        from app.db.models.user import User
        assert hasattr(User, "password_history")


@pytest.mark.asyncio
class TestAccountLockoutLogic:
    """Test lockout logic in auth service."""

    async def test_lockout_increments_on_bad_password(self, db):
        """Failed login should increment failed_login_attempts."""
        from app.db.models.user import User
        from app.core.security import hash_password
        import secrets

        user = User(
            email="locktest@example.com",
            password_hash=hash_password("correct_password"),
            token_key=secrets.token_hex(32),
            failed_login_attempts=0,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        from app.services.auth_service import AuthService
        from app.schemas.auth import UserLogin
        from app.core.exceptions import UnauthorizedException

        service = AuthService(db)
        with pytest.raises(UnauthorizedException):
            await service.login(UserLogin(email="locktest@example.com", password="wrong"))

        await db.refresh(user)
        assert user.failed_login_attempts == 1

    async def test_account_locks_after_max_attempts(self, db):
        """Account should lock after ACCOUNT_LOCKOUT_ATTEMPTS failures."""
        from app.db.models.user import User
        from app.core.security import hash_password
        from app.services.auth_service import AuthService
        from app.schemas.auth import UserLogin
        from app.core.exceptions import UnauthorizedException
        import secrets

        user = User(
            email="locktest2@example.com",
            password_hash=hash_password("correct_password"),
            token_key=secrets.token_hex(32),
            failed_login_attempts=0,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        service = AuthService(db)
        max_attempts = settings.ACCOUNT_LOCKOUT_ATTEMPTS

        for _ in range(max_attempts):
            with pytest.raises(UnauthorizedException):
                await service.login(UserLogin(email="locktest2@example.com", password="wrong"))

        await db.refresh(user)
        assert user.locked_until is not None
        # SQLite returns naive datetimes — normalize before comparison
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        assert locked_until > datetime.now(timezone.utc)

    async def test_locked_account_returns_403(self, db):
        """Locked account should return ForbiddenException."""
        from app.db.models.user import User
        from app.core.security import hash_password
        from app.services.auth_service import AuthService
        from app.schemas.auth import UserLogin
        from app.core.exceptions import ForbiddenException
        import secrets

        user = User(
            email="locked@example.com",
            password_hash=hash_password("correct_password"),
            token_key=secrets.token_hex(32),
            failed_login_attempts=5,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(user)
        await db.commit()

        service = AuthService(db)
        with pytest.raises(ForbiddenException):
            await service.login(UserLogin(email="locked@example.com", password="correct_password"))

    async def test_expired_lockout_resets_automatically(self, db):
        """Expired lockout should auto-reset and allow login."""
        from app.db.models.user import User
        from app.core.security import hash_password
        from app.services.auth_service import AuthService
        from app.schemas.auth import UserLogin
        import secrets

        user = User(
            email="expired@example.com",
            password_hash=hash_password("correct_password"),
            token_key=secrets.token_hex(32),
            failed_login_attempts=5,
            # Lockout expired 1 minute ago
            locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(user)
        await db.commit()

        service = AuthService(db)
        result = await service.login(
            UserLogin(email="expired@example.com", password="correct_password")
        )
        assert result.token.access_token != ""

    async def test_successful_login_resets_counter(self, db):
        """Successful login should reset failed_login_attempts to 0."""
        from app.db.models.user import User
        from app.core.security import hash_password
        from app.services.auth_service import AuthService
        from app.schemas.auth import UserLogin
        import secrets

        user = User(
            email="resettest@example.com",
            password_hash=hash_password("correct_password"),
            token_key=secrets.token_hex(32),
            failed_login_attempts=3,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        service = AuthService(db)
        await service.login(UserLogin(email="resettest@example.com", password="correct_password"))

        await db.refresh(user)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
