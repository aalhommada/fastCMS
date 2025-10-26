"""
Business logic service for authentication operations.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    UnauthorizedException,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_token_type,
)
from app.db.models.user import RefreshToken, User
from app.db.repositories.user import RefreshTokenRepository, UserRepository
from app.schemas.auth import (
    AuthResponse,
    PasswordChange,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)

logger = get_logger(__name__)


class AuthService:
    """Service for managing authentication."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize service.

        Args:
            db: Async database session
        """
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)

    async def register(
        self,
        data: UserRegister,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuthResponse:
        """
        Register a new user.

        Args:
            data: Registration data
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Auth response with user and tokens

        Raises:
            ConflictException: If email already exists
        """
        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(data.email)
        if existing_user:
            raise ConflictException("User with this email already exists")

        # Hash password
        password_hash = hash_password(data.password)

        # Generate token key for session invalidation
        token_key = secrets.token_hex(32)

        # Create user
        user = User(
            email=data.email,
            password_hash=password_hash,
            token_key=token_key,
            name=data.name,
            verified=False,  # Requires email verification
        )

        user = await self.user_repo.create(user)
        await self.db.commit()

        logger.info(f"User registered: {user.email}")

        # Generate tokens
        tokens = await self._create_tokens(user, user_agent, ip_address)

        # TODO: Send verification email
        # await self._send_verification_email(user)

        return AuthResponse(
            user=self._to_user_response(user),
            token=tokens,
        )

    async def login(
        self,
        data: UserLogin,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuthResponse:
        """
        Authenticate user and return tokens.

        Args:
            data: Login credentials
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Auth response with user and tokens

        Raises:
            UnauthorizedException: If credentials are invalid
        """
        # Find user by email
        user = await self.user_repo.get_by_email(data.email)

        if not user:
            raise UnauthorizedException("Invalid email or password")

        # Verify password
        if not verify_password(data.password, user.password_hash):
            logger.warning(f"Failed login attempt for: {data.email}")
            raise UnauthorizedException("Invalid email or password")

        # Check if email is verified (optional - can be configured)
        # if not user.verified:
        #     raise UnauthorizedException("Email not verified")

        logger.info(f"User logged in: {user.email}")

        # Generate tokens
        tokens = await self._create_tokens(user, user_agent, ip_address)

        return AuthResponse(
            user=self._to_user_response(user),
            token=tokens,
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token string
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            New token response

        Raises:
            UnauthorizedException: If refresh token is invalid
        """
        # Decode refresh token
        payload = decode_token(refresh_token)

        if not payload or not verify_token_type(payload, "refresh"):
            raise UnauthorizedException("Invalid refresh token")

        # Get token from database
        token_record = await self.token_repo.get_by_token(refresh_token)

        if not token_record or token_record.revoked:
            raise UnauthorizedException("Refresh token revoked or not found")

        # Check expiry
        expires_at = datetime.fromisoformat(token_record.expires_at)
        if expires_at < datetime.now(timezone.utc):
            raise UnauthorizedException("Refresh token expired")

        # Get user
        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise UnauthorizedException("User not found")

        # Verify token_key hasn't changed (invalidates all sessions)
        if payload.get("token_key") != user.token_key:
            raise UnauthorizedException("Session invalidated")

        logger.info(f"Tokens refreshed for user: {user.email}")

        # Revoke old refresh token (token rotation)
        await self.token_repo.revoke(token_record)

        # Create new tokens
        return await self._create_tokens(user, user_agent, ip_address)

    async def logout(self, refresh_token: str) -> None:
        """
        Logout user by revoking refresh token.

        Args:
            refresh_token: Refresh token to revoke
        """
        token_record = await self.token_repo.get_by_token(refresh_token)

        if token_record and not token_record.revoked:
            await self.token_repo.revoke(token_record)
            await self.db.commit()
            logger.info(f"User logged out: {token_record.user_id}")

    async def logout_all(self, user_id: str) -> None:
        """
        Logout user from all devices by revoking all tokens.

        Args:
            user_id: User ID
        """
        await self.token_repo.revoke_all_for_user(user_id)
        await self.db.commit()
        logger.info(f"All sessions revoked for user: {user_id}")

    async def get_user(self, user_id: str) -> UserResponse:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User response

        Raises:
            UnauthorizedException: If user not found
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise UnauthorizedException("User not found")

        return self._to_user_response(user)

    async def update_user(
        self,
        user_id: str,
        data: UserUpdate,
    ) -> UserResponse:
        """
        Update user profile.

        Args:
            user_id: User ID
            data: Update data

        Returns:
            Updated user response

        Raises:
            UnauthorizedException: If user not found
            ConflictException: If email already taken
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise UnauthorizedException("User not found")

        # Update fields
        if data.email is not None and data.email != user.email:
            # Check email uniqueness
            existing = await self.user_repo.get_by_email(data.email)
            if existing:
                raise ConflictException("Email already taken")
            user.email = data.email
            user.verified = False  # Require re-verification

        if data.name is not None:
            user.name = data.name

        if data.avatar is not None:
            user.avatar = data.avatar

        if data.email_visibility is not None:
            user.email_visibility = data.email_visibility

        user = await self.user_repo.update(user)
        await self.db.commit()

        logger.info(f"User updated: {user.email}")

        return self._to_user_response(user)

    async def change_password(
        self,
        user_id: str,
        data: PasswordChange,
    ) -> None:
        """
        Change user password.

        Args:
            user_id: User ID
            data: Password change data

        Raises:
            UnauthorizedException: If user not found or old password incorrect
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise UnauthorizedException("User not found")

        # Verify old password
        if not verify_password(data.old_password, user.password_hash):
            raise UnauthorizedException("Incorrect password")

        # Hash new password
        user.password_hash = hash_password(data.new_password)

        # Generate new token key to invalidate all sessions
        user.token_key = secrets.token_hex(32)

        await self.user_repo.update(user)
        await self.db.commit()

        # Revoke all refresh tokens
        await self.token_repo.revoke_all_for_user(user_id)
        await self.db.commit()

        logger.info(f"Password changed for user: {user.email}")

    async def _create_tokens(
        self,
        user: User,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """
        Create access and refresh tokens for user.

        Args:
            user: User instance
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Token response
        """
        # Create access token
        access_token = create_access_token(
            data={"sub": user.id, "email": user.email, "token_key": user.token_key}
        )

        # Create refresh token
        refresh_token_str = create_refresh_token(
            data={"sub": user.id, "token_key": user.token_key}
        )

        # Store refresh token in database
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=expires_at.isoformat(),
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await self.token_repo.create(refresh_token)
        await self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def _to_user_response(self, user: User) -> UserResponse:
        """
        Convert user model to response schema.

        Args:
            user: User model

        Returns:
            User response schema
        """
        return UserResponse(
            id=user.id,
            email=user.email if user.email_visibility else "hidden",
            verified=user.verified,
            name=user.name,
            avatar=user.avatar,
            created=user.created,
            updated=user.updated,
        )
