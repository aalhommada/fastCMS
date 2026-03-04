"""Repository for email verification and password reset tokens."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.verification import PasswordResetToken, VerificationToken


class VerificationTokenRepository:
    """Repository for email verification tokens."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, token: VerificationToken) -> VerificationToken:
        """Create verification token."""
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_by_token(self, token: str) -> Optional[VerificationToken]:
        """Get verification token by token string."""
        stmt = select(VerificationToken).where(VerificationToken.token == token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> Optional[VerificationToken]:
        """Get latest verification token for user."""
        stmt = (
            select(VerificationToken)
            .where(VerificationToken.user_id == user_id)
            .where(VerificationToken.used == False)
            .order_by(VerificationToken.created.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, token: VerificationToken) -> VerificationToken:
        """Mark token as used."""
        token.used = True
        await self.db.flush()
        return token

    async def is_valid(self, token: VerificationToken) -> bool:
        """Check if token is valid (not used and not expired)."""
        if token.used:
            return False

        expires_at = datetime.fromisoformat(token.expires_at)
        return expires_at > datetime.now(timezone.utc)

    async def get_latest_otp(self, user_id: str, code: str) -> Optional[VerificationToken]:
        """Get the latest valid OTP token for a user matching the given code."""
        stmt = (
            select(VerificationToken)
            .where(VerificationToken.user_id == user_id)
            .where(VerificationToken.token == code)
            .where(VerificationToken.token_type == "otp")
            .where(VerificationToken.used == False)
            .order_by(VerificationToken.created.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_for_user(self, user_id: str) -> None:
        """Delete all verification tokens for a user."""
        stmt = select(VerificationToken).where(VerificationToken.user_id == user_id)
        result = await self.db.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            await self.db.delete(token)

        await self.db.flush()


class PasswordResetTokenRepository:
    """Repository for password reset tokens."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        """Create password reset token."""
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_by_token(self, token: str) -> Optional[PasswordResetToken]:
        """Get password reset token by token string."""
        stmt = select(PasswordResetToken).where(PasswordResetToken.token == token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> Optional[PasswordResetToken]:
        """Get latest password reset token for user."""
        stmt = (
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id)
            .where(PasswordResetToken.used == False)
            .order_by(PasswordResetToken.created.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, token: PasswordResetToken) -> PasswordResetToken:
        """Mark token as used."""
        token.used = True
        await self.db.flush()
        return token

    async def is_valid(self, token: PasswordResetToken) -> bool:
        """Check if token is valid (not used and not expired)."""
        if token.used:
            return False

        expires_at = datetime.fromisoformat(token.expires_at)
        return expires_at > datetime.now(timezone.utc)

    async def delete_for_user(self, user_id: str) -> None:
        """Delete all password reset tokens for a user."""
        stmt = select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
        result = await self.db.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            await self.db.delete(token)

        await self.db.flush()
