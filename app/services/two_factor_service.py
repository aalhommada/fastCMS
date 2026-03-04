"""
Two-Factor Authentication (2FA) Service using TOTP.

Provides TOTP-based 2FA with backup codes for account recovery.
"""

import base64
import hashlib
import io
import secrets
from typing import List, Optional, Tuple

import pyotp
import qrcode
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.repositories.user import UserRepository

logger = get_logger(__name__)

# Number of backup codes to generate
BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 8


class TwoFactorService:
    """Service for managing Two-Factor Authentication."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def generate_setup(self, user_id: str) -> dict:
        """
        Generate 2FA setup data (secret + QR code).

        Args:
            user_id: User ID

        Returns:
            Dict with secret, qr_code (base64), and otpauth_url
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("User not found")

        if user.two_factor_enabled:
            raise BadRequestException("2FA is already enabled")

        # Generate new TOTP secret
        secret = pyotp.random_base32()

        # Create TOTP instance
        totp = pyotp.TOTP(secret)

        # Generate provisioning URI for QR code
        issuer = settings.APP_NAME
        otpauth_url = totp.provisioning_uri(
            name=user.email,
            issuer_name=issuer
        )

        # Generate QR code as base64
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(otpauth_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Store the secret temporarily (not enabled yet)
        user.two_factor_secret = secret
        await self.db.commit()

        logger.info(f"2FA setup generated for user {user_id}")

        return {
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_base64}",
            "otpauth_url": otpauth_url,
        }

    async def enable(self, user_id: str, code: str) -> dict:
        """
        Enable 2FA after verifying the code.

        Args:
            user_id: User ID
            code: TOTP code to verify

        Returns:
            Dict with backup_codes
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("User not found")

        if user.two_factor_enabled:
            raise BadRequestException("2FA is already enabled")

        if not user.two_factor_secret:
            raise BadRequestException("2FA setup not initiated. Call /2fa/setup first")

        # Verify the code
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(code, valid_window=1):
            raise BadRequestException("Invalid verification code")

        # Generate backup codes
        backup_codes = self._generate_backup_codes()
        hashed_codes = [self._hash_backup_code(c) for c in backup_codes]

        # Enable 2FA
        user.two_factor_enabled = True
        user.two_factor_backup_codes = ",".join(hashed_codes)
        await self.db.commit()

        logger.info(f"2FA enabled for user {user_id}")

        # Notify user (fire-and-forget)
        from app.core.config import settings
        if settings.SMTP_ENABLED and settings.SECURITY_NOTIFICATIONS_ENABLED:
            import asyncio
            from app.services.email_service import EmailService
            asyncio.create_task(EmailService.send_2fa_enabled_notification(user.email))

        return {
            "enabled": True,
            "backup_codes": backup_codes,
            "message": "2FA enabled successfully. Save your backup codes securely."
        }

    async def disable(self, user_id: str, code: str) -> dict:
        """
        Disable 2FA after verifying the code.

        Args:
            user_id: User ID
            code: TOTP code or backup code

        Returns:
            Success message
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("User not found")

        if not user.two_factor_enabled:
            raise BadRequestException("2FA is not enabled")

        # Verify the code (TOTP or backup code)
        if not await self._verify_code(user, code):
            raise BadRequestException("Invalid verification code")

        # Disable 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        await self.db.commit()

        logger.info(f"2FA disabled for user {user_id}")

        # Notify user (fire-and-forget)
        from app.core.config import settings
        if settings.SMTP_ENABLED and settings.SECURITY_NOTIFICATIONS_ENABLED:
            import asyncio
            from app.services.email_service import EmailService
            asyncio.create_task(EmailService.send_2fa_disabled_notification(user.email))

        return {
            "enabled": False,
            "message": "2FA has been disabled"
        }

    async def verify(self, user_id: str, code: str) -> bool:
        """
        Verify a 2FA code (TOTP or backup code).

        Args:
            user_id: User ID
            code: TOTP code or backup code

        Returns:
            True if valid
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("User not found")

        if not user.two_factor_enabled:
            return True  # 2FA not enabled, auto-pass

        return await self._verify_code(user, code)

    async def verify_login(self, user: User, code: str) -> bool:
        """
        Verify 2FA code during login.

        Args:
            user: User object
            code: TOTP code or backup code

        Returns:
            True if valid

        Raises:
            UnauthorizedException if invalid
        """
        if not user.two_factor_enabled:
            return True

        if not await self._verify_code(user, code):
            raise UnauthorizedException("Invalid 2FA code")

        return True

    async def regenerate_backup_codes(self, user_id: str, code: str) -> dict:
        """
        Regenerate backup codes after verifying current code.

        Args:
            user_id: User ID
            code: Current TOTP code

        Returns:
            New backup codes
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("User not found")

        if not user.two_factor_enabled:
            raise BadRequestException("2FA is not enabled")

        # Verify the TOTP code (not backup code for regeneration)
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(code, valid_window=1):
            raise BadRequestException("Invalid verification code")

        # Generate new backup codes
        backup_codes = self._generate_backup_codes()
        hashed_codes = [self._hash_backup_code(c) for c in backup_codes]

        user.two_factor_backup_codes = ",".join(hashed_codes)
        await self.db.commit()

        logger.info(f"Backup codes regenerated for user {user_id}")

        return {
            "backup_codes": backup_codes,
            "message": "New backup codes generated. Previous codes are now invalid."
        }

    async def get_status(self, user_id: str) -> dict:
        """
        Get 2FA status for a user.

        Args:
            user_id: User ID

        Returns:
            2FA status info
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise BadRequestException("User not found")

        backup_codes_remaining = 0
        if user.two_factor_backup_codes:
            backup_codes_remaining = len(user.two_factor_backup_codes.split(","))

        return {
            "enabled": user.two_factor_enabled,
            "backup_codes_remaining": backup_codes_remaining if user.two_factor_enabled else 0,
        }

    async def _verify_code(self, user: User, code: str) -> bool:
        """
        Verify a code (TOTP or backup code).

        Args:
            user: User object
            code: Code to verify

        Returns:
            True if valid
        """
        # Clean the code
        code = code.strip().replace(" ", "").replace("-", "")

        # Try TOTP first (6 digits)
        if len(code) == 6 and code.isdigit():
            totp = pyotp.TOTP(user.two_factor_secret)
            if totp.verify(code, valid_window=1):
                return True

        # Try backup code
        if user.two_factor_backup_codes:
            hashed_code = self._hash_backup_code(code)
            codes = user.two_factor_backup_codes.split(",")

            if hashed_code in codes:
                # Remove used backup code
                codes.remove(hashed_code)
                user.two_factor_backup_codes = ",".join(codes) if codes else None
                await self.db.commit()
                logger.info(f"Backup code used for user {user.id}")
                return True

        return False

    def _generate_backup_codes(self) -> List[str]:
        """Generate a list of backup codes."""
        codes = []
        for _ in range(BACKUP_CODE_COUNT):
            # Generate random code (e.g., "a1b2-c3d4")
            code = secrets.token_hex(BACKUP_CODE_LENGTH // 2)
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes

    def _hash_backup_code(self, code: str) -> str:
        """Hash a backup code for storage."""
        # Clean the code
        clean_code = code.strip().replace("-", "").replace(" ", "").lower()
        return hashlib.sha256(clean_code.encode()).hexdigest()[:32]
