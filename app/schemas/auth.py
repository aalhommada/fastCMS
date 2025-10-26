"""
Pydantic schemas for authentication endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


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
    created: datetime
    updated: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Schema for auth response with user and tokens."""

    user: UserResponse
    token: TokenResponse


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
