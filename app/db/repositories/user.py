"""
Repository for User and RefreshToken database operations.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import RefreshToken, User


class UserRepository:
    """Repository for user CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            db: Async database session
        """
        self.db = db

    async def create(self, user: User) -> User:
        """
        Create a new user.

        Args:
            user: User instance to create

        Returns:
            Created user
        """
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User or None if not found
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def update(self, user: User) -> User:
        """
        Update a user.

        Args:
            user: User instance with updated data

        Returns:
            Updated user
        """
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """
        Delete a user.

        Args:
            user: User to delete
        """
        await self.db.delete(user)
        await self.db.flush()


class RefreshTokenRepository:
    """Repository for refresh token operations."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            db: Async database session
        """
        self.db = db

    async def create(self, refresh_token: RefreshToken) -> RefreshToken:
        """
        Create a new refresh token.

        Args:
            refresh_token: RefreshToken instance to create

        Returns:
            Created refresh token
        """
        self.db.add(refresh_token)
        await self.db.flush()
        await self.db.refresh(refresh_token)
        return refresh_token

    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        """
        Get refresh token by token string.

        Args:
            token: Token string

        Returns:
            RefreshToken or None if not found
        """
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()

    async def revoke(self, refresh_token: RefreshToken) -> RefreshToken:
        """
        Revoke a refresh token.

        Args:
            refresh_token: RefreshToken to revoke

        Returns:
            Revoked token
        """
        refresh_token.revoked = True
        await self.db.flush()
        await self.db.refresh(refresh_token)
        return refresh_token

    async def revoke_all_for_user(self, user_id: str) -> None:
        """
        Revoke all refresh tokens for a user.

        Args:
            user_id: User ID
        """
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
            )
        )
        tokens = result.scalars().all()

        for token in tokens:
            token.revoked = True

        await self.db.flush()

    async def delete_expired(self) -> int:
        """
        Delete expired refresh tokens.

        Returns:
            Number of tokens deleted
        """
        now = datetime.now(timezone.utc).isoformat()

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.expires_at < now)
        )
        tokens = result.scalars().all()

        count = len(tokens)
        for token in tokens:
            await self.db.delete(token)

        await self.db.flush()
        return count
