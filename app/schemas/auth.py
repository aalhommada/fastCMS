"""
Pydantic schemas for authentication endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class UserRegister(BaseModel):
    """Schema for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password (min 8 chars)")
    password_confirm: str = Field(..., description="Password confirmation")
    name: Optional[str] = Field(None, max_length=255, description="Display name")

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info: any) -> str:
        """Validate passwords match."""
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        # Check for at least one letter and one number
        has_letter = any(c.isalpha() for c in v)
        has_number = any(c.isdigit() for c in v)

        if not (has_letter and has_number):
            raise ValueError("Password must contain at least one letter and one number")

        return v


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    two_factor_code: Optional[str] = Field(None, description="2FA code (if enabled)")


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """Schema for user response (public data)."""

    id: str
    email: str
    verified: bool
    name: Optional[str]
    avatar: Optional[str]
    role: str
    two_factor_enabled: bool = False
    created: datetime
    updated: datetime
    message: Optional[str] = None

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Schema for auth response with user and tokens."""

    user: UserResponse
    token: TokenResponse
    message: Optional[str] = None
    requires_2fa: bool = False  # True if 2FA is needed to complete login


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr = Field(..., description="User email address")


class PasswordReset(BaseModel):
    """Schema for password reset with token."""

    token: str = Field(..., description="Password reset token")
    password: str = Field(..., min_length=8, max_length=100, description="New password")
    password_confirm: str = Field(..., description="Password confirmation")

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info: any) -> str:
        """Validate passwords match."""
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class EmailVerification(BaseModel):
    """Schema for email verification."""

    token: str = Field(..., description="Email verification token")


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None
    email_visibility: Optional[bool] = None


class PasswordChange(BaseModel):
    """Schema for changing password."""

    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")
    new_password_confirm: str = Field(..., description="New password confirmation")

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info: any) -> str:
        """Validate passwords match."""
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class UserAdminCreate(BaseModel):
    """Schema for admin creating a user."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password (min 8 chars)")
    name: Optional[str] = Field(None, max_length=255, description="Display name")
    role: str = Field(default="user", pattern="^(user|admin)$", description="User role")
    verified: bool = Field(default=False, description="Email verified status")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        # Check for at least one letter and one number
        has_letter = any(c.isalpha() for c in v)
        has_number = any(c.isdigit() for c in v)

        if not (has_letter and has_number):
            raise ValueError("Password must contain at least one letter and one number")

        return v


class UserAdminUpdate(BaseModel):
    """Schema for admin updating a user."""

    email: Optional[EmailStr] = None
    name: Optional[str] = Field(None, max_length=255)
    avatar: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(user|admin)$")
    verified: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: Optional[str]) -> Optional[str]:
        """Validate password strength."""
        if v is None:
            return v

        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        # Check for at least one letter and one number
        has_letter = any(c.isalpha() for c in v)
        has_number = any(c.isdigit() for c in v)

        if not (has_letter and has_number):
            raise ValueError("Password must contain at least one letter and one number")

        return v


# ===== Two-Factor Authentication Schemas =====

class TwoFactorSetupResponse(BaseModel):
    """Response for 2FA setup initiation."""

    secret: str = Field(..., description="TOTP secret key (base32)")
    qr_code: str = Field(..., description="QR code as base64 data URL")
    otpauth_url: str = Field(..., description="OTPAuth URL for manual entry")


class TwoFactorVerifyRequest(BaseModel):
    """Request to verify/enable 2FA."""

    code: str = Field(..., min_length=6, max_length=10, description="6-digit TOTP code")


class TwoFactorEnableResponse(BaseModel):
    """Response after enabling 2FA."""

    enabled: bool = True
    backup_codes: list[str] = Field(..., description="One-time backup codes")
    message: str


class TwoFactorDisableRequest(BaseModel):
    """Request to disable 2FA."""

    code: str = Field(..., description="TOTP code or backup code")


class TwoFactorStatusResponse(BaseModel):
    """2FA status response."""

    enabled: bool
    backup_codes_remaining: int = 0


class TwoFactorBackupCodesResponse(BaseModel):
    """Response with new backup codes."""

    backup_codes: list[str]
    message: str


# ===== Email Change Schemas =====

class EmailChangeRequest(BaseModel):
    """Request to initiate an email address change."""

    new_email: EmailStr = Field(..., description="New email address to change to")
    password: str = Field(..., description="Current password to confirm identity")


class EmailChangeConfirm(BaseModel):
    """Confirm email change with token sent to new address."""

    token: str = Field(..., description="Token received at the new email address")


# ===== OTP (One-Time Password) Auth Schemas =====

class OTPRequest(BaseModel):
    """Request a one-time password sent via email."""

    email: EmailStr = Field(..., description="Email address to send OTP to")


class OTPVerify(BaseModel):
    """Verify OTP and complete passwordless authentication."""

    email: EmailStr = Field(..., description="Email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


# ===== Impersonation Schema =====

class ImpersonationResponse(BaseModel):
    """Response for user impersonation (admin only). No refresh token issued."""

    access_token: str = Field(..., description="Short-lived access token for the target user")
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")
    impersonated_user_id: str
    message: str = "Impersonation token issued. This token cannot be refreshed."
