"""
Business logic service for authentication operations.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_policy,
    verify_password,
    verify_token_type,
)
from app.db.models.user import RefreshToken, User
from app.db.models.verification import PasswordResetToken, VerificationToken
from app.db.repositories.user import RefreshTokenRepository, UserRepository
from app.db.repositories.verification import (
    PasswordResetTokenRepository,
    VerificationTokenRepository,
)
from app.schemas.auth import (
    AuthResponse,
    PasswordChange,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.services.email_service import EmailService

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
        self.verification_repo = VerificationTokenRepository(db)
        self.reset_repo = PasswordResetTokenRepository(db)

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

        # Validate password policy
        policy_errors = validate_password_policy(data.password)
        if policy_errors:
            raise BadRequestException(f"Password policy violation: {'; '.join(policy_errors)}")

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

        # Send verification email
        if settings.SMTP_ENABLED:
            await self._send_verification_email(user)

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

        # Check account lockout
        if settings.ACCOUNT_LOCKOUT_ENABLED and user.locked_until:
            now = datetime.now(timezone.utc)
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                remaining = int((locked_until - now).total_seconds())
                raise ForbiddenException(
                    f"Account locked due to too many failed attempts. "
                    f"Try again in {remaining} seconds."
                )
            else:
                # Lockout expired — reset counter
                user.failed_login_attempts = 0
                user.locked_until = None

        # Verify password
        if not verify_password(data.password, user.password_hash):
            logger.warning(f"Failed login attempt for: {data.email}")
            if settings.ACCOUNT_LOCKOUT_ENABLED:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(
                        seconds=settings.ACCOUNT_LOCKOUT_DURATION
                    )
                    logger.warning(
                        f"Account locked for {data.email} after "
                        f"{user.failed_login_attempts} failed attempts"
                    )
                    # Notify user of account lockout
                    if settings.SMTP_ENABLED and settings.SECURITY_NOTIFICATIONS_ENABLED:
                        import asyncio
                        lockout_minutes = settings.ACCOUNT_LOCKOUT_DURATION // 60
                        asyncio.create_task(
                            EmailService.send_account_locked_notification(
                                user.email, lockout_minutes, settings.BASE_URL
                            )
                        )
                await self.user_repo.update(user)
                await self.db.commit()
            raise UnauthorizedException("Invalid email or password")

        # Successful login — reset lockout counter
        if settings.ACCOUNT_LOCKOUT_ENABLED and user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
            user.locked_until = None
            await self.user_repo.update(user)

        # Check if email is verified (optional - can be configured)
        # if not user.verified:
        #     raise UnauthorizedException("Email not verified")

        # Check 2FA requirement
        if user.two_factor_enabled:
            if not data.two_factor_code:
                # Return response indicating 2FA is required
                logger.info(f"2FA required for: {user.email}")
                return AuthResponse(
                    user=self._to_user_response(user),
                    token=TokenResponse(
                        access_token="",
                        refresh_token="",
                        token_type="bearer",
                        expires_in=0,
                    ),
                    requires_2fa=True,
                    message="Two-factor authentication required",
                )

            # Verify 2FA code
            from app.services.two_factor_service import TwoFactorService
            two_factor_service = TwoFactorService(self.db)
            if not await two_factor_service._verify_code(user, data.two_factor_code):
                logger.warning(f"Invalid 2FA code for: {data.email}")
                raise UnauthorizedException("Invalid two-factor authentication code")

        logger.info(f"User logged in: {user.email}")

        # Generate tokens
        tokens = await self._create_tokens(user, user_agent, ip_address)

        # Optional: send login notification (fire-and-forget)
        if (settings.SMTP_ENABLED and settings.SECURITY_NOTIFICATIONS_ENABLED
                and settings.SECURITY_LOGIN_NOTIFICATIONS and ip_address):
            import asyncio
            asyncio.create_task(
                EmailService.send_login_notification(
                    user.email, ip_address, user_agent or "Unknown", settings.BASE_URL
                )
            )

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
        ip_address: Optional[str] = None,
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

        # Validate password policy
        policy_errors = validate_password_policy(data.new_password)
        if policy_errors:
            raise BadRequestException(f"Password policy violation: {'; '.join(policy_errors)}")

        # Check password history
        self._check_password_history(user, data.new_password)

        # Store current hash in history before changing
        self._update_password_history(user)

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

        # Notify user
        if settings.SMTP_ENABLED and settings.SECURITY_NOTIFICATIONS_ENABLED:
            import asyncio
            asyncio.create_task(
                EmailService.send_password_changed_notification(
                    user.email, ip_address or "Unknown", settings.BASE_URL
                )
            )

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

    async def verify_email(self, token: str) -> None:
        """
        Verify user email with token.

        Args:
            token: Verification token

        Raises:
            BadRequestException: If token is invalid or expired
        """
        token_record = await self.verification_repo.get_by_token(token)

        if not token_record:
            raise BadRequestException("Invalid verification token")

        if not await self.verification_repo.is_valid(token_record):
            raise BadRequestException("Verification token expired or already used")

        # Get user
        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user:
            raise BadRequestException("User not found")

        # Mark user as verified
        user.verified = True
        await self.user_repo.update(user)

        # Mark token as used
        await self.verification_repo.mark_used(token_record)
        await self.db.commit()

        logger.info(f"Email verified for user: {user.email}")

    async def resend_verification(self, user_id: str) -> None:
        """
        Resend verification email to user.

        Args:
            user_id: User ID

        Raises:
            BadRequestException: If user already verified or SMTP not enabled
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("User not found")

        if user.verified:
            raise BadRequestException("Email already verified")

        if not settings.SMTP_ENABLED:
            raise BadRequestException("Email service not configured")

        await self._send_verification_email(user)
        logger.info(f"Verification email resent to: {user.email}")

    async def request_password_reset(self, email: str) -> None:
        """
        Request password reset for user.

        Args:
            email: User email address

        Note:
            Always returns success to prevent email enumeration
        """
        user = await self.user_repo.get_by_email(email)

        # Don't reveal if email exists (prevent enumeration)
        if not user or not settings.SMTP_ENABLED:
            logger.info(f"Password reset requested for non-existent or unconfigured email: {email}")
            return

        # Generate reset token
        token = EmailService.generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at.isoformat(),
        )

        await self.reset_repo.create(reset_token)
        await self.db.commit()

        # Send reset email
        await EmailService.send_password_reset_email(
            user.email, token, settings.BASE_URL
        )

        logger.info(f"Password reset email sent to: {user.email}")

    async def reset_password(self, token: str, new_password: str) -> None:
        """
        Reset user password with token.

        Args:
            token: Password reset token
            new_password: New password

        Raises:
            BadRequestException: If token is invalid or expired
        """
        token_record = await self.reset_repo.get_by_token(token)

        if not token_record:
            raise BadRequestException("Invalid reset token")

        if not await self.reset_repo.is_valid(token_record):
            raise BadRequestException("Reset token expired or already used")

        # Get user
        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user:
            raise BadRequestException("User not found")

        # Validate password policy
        policy_errors = validate_password_policy(new_password)
        if policy_errors:
            raise BadRequestException(f"Password policy violation: {'; '.join(policy_errors)}")

        # Check password history
        self._check_password_history(user, new_password)
        self._update_password_history(user)

        # Update password
        user.password_hash = hash_password(new_password)

        # Generate new token key to invalidate all sessions
        user.token_key = secrets.token_hex(32)

        await self.user_repo.update(user)

        # Mark token as used
        await self.reset_repo.mark_used(token_record)

        # Revoke all refresh tokens
        await self.token_repo.revoke_all_for_user(user.id)
        await self.db.commit()

        logger.info(f"Password reset for user: {user.email}")

        # Notify user
        if settings.SMTP_ENABLED and settings.SECURITY_NOTIFICATIONS_ENABLED:
            import asyncio
            asyncio.create_task(
                EmailService.send_password_changed_notification(
                    user.email, "password reset flow", settings.BASE_URL
                )
            )

    async def get_sessions(self, user_id: str) -> list[dict]:
        """
        Get all active sessions for a user.

        Args:
            user_id: User ID

        Returns:
            List of session dictionaries with id, user_agent, ip_address, and created
        """
        # Get all non-revoked refresh tokens for the user
        tokens = await self.token_repo.get_all_for_user(user_id)

        sessions = []
        for token in tokens:
            if not token.revoked:
                sessions.append({
                    "id": token.id,
                    "user_agent": token.user_agent or "Unknown",
                    "ip_address": token.ip_address or "Unknown",
                    "created": token.created,
                    "expires_at": token.expires_at,
                })

        return sessions

    async def revoke_session(self, user_id: str, session_id: str) -> None:
        """
        Revoke a specific session (refresh token) for a user.

        Args:
            user_id: User ID
            session_id: Session (refresh token) ID

        Raises:
            UnauthorizedException: If session not found or doesn't belong to user
        """
        # Get the refresh token
        token = await self.token_repo.get_by_id(session_id)
        if not token or token.user_id != user_id:
            raise UnauthorizedException("Session not found")

        # Revoke the token
        await self.token_repo.revoke(token)
        await self.db.commit()

        logger.info(f"Session {session_id} revoked for user {user_id}")

    async def delete_user(self, user_id: str) -> None:
        """
        Delete a user account and all associated data.

        Args:
            user_id: User ID to delete

        Raises:
            UnauthorizedException: If user not found
        """
        # Get the user
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException("User not found")

        # Revoke all refresh tokens
        await self.token_repo.revoke_all_for_user(user_id)

        # Delete verification tokens
        await self.verification_repo.delete_for_user(user_id)

        # Delete password reset tokens
        await self.reset_repo.delete_for_user(user_id)

        # Delete the user
        await self.user_repo.delete(user)
        await self.db.commit()

        logger.info(f"User account deleted: {user.email}")

    async def request_email_change(self, user_id: str, new_email: str, password: str) -> None:
        """
        Initiate an email change. Sends a confirmation token to the NEW email.

        Args:
            user_id: Current user's ID
            new_email: New email address the user wants to switch to
            password: Current password for identity verification

        Raises:
            UnauthorizedException: If password is wrong
            ConflictException: If new email is already in use
            BadRequestException: If SMTP is not configured
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException("User not found")

        if not verify_password(password, user.password_hash):
            raise UnauthorizedException("Incorrect password")

        if new_email.lower() == user.email.lower():
            raise BadRequestException("New email must differ from current email")

        existing = await self.user_repo.get_by_email(new_email)
        if existing:
            raise ConflictException("This email address is already in use")

        if not settings.SMTP_ENABLED:
            raise BadRequestException("Email service not configured")

        token = EmailService.generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        verification_token = VerificationToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at.isoformat(),
            token_type="email_change",
            new_email=new_email,
        )
        await self.verification_repo.create(verification_token)
        await self.db.commit()

        await EmailService.send_email_change_confirmation(new_email, token, settings.BASE_URL)
        logger.info(f"Email change requested for user {user.email} → {new_email}")

    async def confirm_email_change(self, token: str) -> None:
        """
        Confirm email change using the token sent to the new address.

        Args:
            token: Email change confirmation token

        Raises:
            BadRequestException: If token is invalid, expired, or already used
        """
        token_record = await self.verification_repo.get_by_token(token)

        if not token_record or token_record.token_type != "email_change":
            raise BadRequestException("Invalid email change token")

        if not await self.verification_repo.is_valid(token_record):
            raise BadRequestException("Token has expired or already been used")

        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user:
            raise BadRequestException("User not found")

        # Confirm new email is still available
        new_email = token_record.new_email
        if not new_email:
            raise BadRequestException("Invalid token: missing new email")

        existing = await self.user_repo.get_by_email(new_email)
        if existing and existing.id != user.id:
            raise ConflictException("This email address is already in use")

        old_email = user.email
        user.email = new_email
        user.verified = True
        await self.user_repo.update(user)

        await self.verification_repo.mark_used(token_record)
        await self.db.commit()

        logger.info(f"Email changed: {old_email} → {new_email}")

    async def request_otp(self, email: str) -> None:
        """
        Send a 6-digit OTP code to the given email for passwordless login.
        Always returns success (prevents email enumeration).

        Args:
            email: Email address to send OTP to
        """
        import random

        user = await self.user_repo.get_by_email(email)
        if not user or not settings.SMTP_ENABLED:
            logger.info(f"OTP requested for unknown/unconfigured email: {email}")
            return

        code = f"{random.randint(0, 999999):06d}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        otp_token = VerificationToken(
            user_id=user.id,
            token=code,
            expires_at=expires_at.isoformat(),
            token_type="otp",
        )
        await self.verification_repo.create(otp_token)
        await self.db.commit()

        await EmailService.send_otp_email(email, code, settings.BASE_URL)
        logger.info(f"OTP sent to: {email}")

    async def auth_with_otp(
        self,
        email: str,
        code: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> "AuthResponse":
        """
        Authenticate user with OTP code. Returns full AuthResponse on success.

        Args:
            email: User's email address
            code: 6-digit OTP code
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            AuthResponse with user and tokens

        Raises:
            UnauthorizedException: If code is invalid or expired
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UnauthorizedException("Invalid or expired OTP code")

        # Find the most recent unused OTP for this user
        token_record = await self.verification_repo.get_latest_otp(user.id, code)
        if not token_record or not await self.verification_repo.is_valid(token_record):
            raise UnauthorizedException("Invalid or expired OTP code")

        # Mark token used
        await self.verification_repo.mark_used(token_record)

        # Auto-verify email on successful OTP login
        if not user.verified:
            user.verified = True
            await self.user_repo.update(user)

        await self.db.commit()

        tokens = await self._create_tokens(user, user_agent, ip_address)
        logger.info(f"OTP login successful for: {email}")

        from app.schemas.auth import AuthResponse
        return AuthResponse(user=self._to_user_response(user), token=tokens)

    def _check_password_history(self, user: User, new_password: str) -> None:
        """
        Check that new password was not used recently.

        Args:
            user: User model
            new_password: New plain text password

        Raises:
            BadRequestException: If password was used recently
        """
        import json
        history_count = settings.PASSWORD_HISTORY_COUNT
        if history_count == 0:
            return

        history: list[str] = []
        if user.password_history:
            try:
                history = json.loads(user.password_history)
            except (ValueError, TypeError):
                history = []

        # Also check current password
        if verify_password(new_password, user.password_hash):
            raise BadRequestException("New password must differ from current password")

        for old_hash in history[:history_count]:
            if verify_password(new_password, old_hash):
                raise BadRequestException(
                    f"Password was used recently. Choose a password not used in the last "
                    f"{history_count} changes."
                )

    def _update_password_history(self, user: User) -> None:
        """
        Add current password hash to history before changing password.

        Args:
            user: User model (mutated in place)
        """
        import json
        history_count = settings.PASSWORD_HISTORY_COUNT
        if history_count == 0:
            return

        history: list[str] = []
        if user.password_history:
            try:
                history = json.loads(user.password_history)
            except (ValueError, TypeError):
                history = []

        # Prepend current hash and trim to limit
        history = [user.password_hash] + history
        user.password_history = json.dumps(history[:history_count])

    async def _send_verification_email(self, user: User) -> None:
        """
        Send verification email to user.

        Args:
            user: User instance
        """
        # Generate verification token
        token = EmailService.generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        verification_token = VerificationToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at.isoformat(),
        )

        await self.verification_repo.create(verification_token)
        await self.db.commit()

        # Send email
        await EmailService.send_verification_email(
            user.email, token, settings.BASE_URL
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
            role=user.role,
            created=user.created,
            updated=user.updated,
        )
