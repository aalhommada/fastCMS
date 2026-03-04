"""
Models for email verification and password reset tokens.
"""

from typing import Optional
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class VerificationToken(BaseModel):
    """Email verification token model."""

    __tablename__ = "verification_tokens"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    expires_at: Mapped[str] = mapped_column(String(50), nullable=False)

    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Token type: "email_verification" (default) | "email_change" | "otp"
    token_type: Mapped[str] = mapped_column(String(30), nullable=False, default="email_verification")

    # For email_change tokens: store the new email being confirmed
    new_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)


class PasswordResetToken(BaseModel):
    """Password reset token model."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    expires_at: Mapped[str] = mapped_column(String(50), nullable=False)

    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
