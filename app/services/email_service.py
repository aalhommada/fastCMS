"""
Email service for sending verification and password reset emails.
"""

import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    async def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email

        Returns:
            True if email sent successfully, False otherwise
        """
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP not configured, email not sent")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    @staticmethod
    async def send_verification_email(
        to_email: str, verification_token: str, base_url: str = "http://localhost:8000"
    ) -> bool:
        """
        Send email verification email.

        Args:
            to_email: User email address
            verification_token: Verification token
            base_url: Base URL of the application

        Returns:
            True if email sent successfully
        """
        verification_url = f"{base_url}/api/v1/auth/verify-email?token={verification_token}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Verify Your Email Address</h2>
            <p>Thank you for registering with {settings.APP_NAME}!</p>
            <p>Please click the button below to verify your email address:</p>
            <p style="margin: 30px 0;">
                <a href="{verification_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    Verify Email Address
                </a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #666;">{verification_url}</p>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't create an account, you can safely ignore this email.</p>
        </body>
        </html>
        """

        return await EmailService.send_email(
            to_email=to_email,
            subject=f"Verify your {settings.APP_NAME} account",
            html_content=html_content,
        )

    @staticmethod
    async def send_password_reset_email(
        to_email: str, reset_token: str, base_url: str = "http://localhost:8000"
    ) -> bool:
        """
        Send password reset email.

        Args:
            to_email: User email address
            reset_token: Password reset token
            base_url: Base URL of the application

        Returns:
            True if email sent successfully
        """
        reset_url = f"{base_url}/auth/reset-password?token={reset_token}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Reset Your Password</h2>
            <p>We received a request to reset your password for your {settings.APP_NAME} account.</p>
            <p>Click the button below to reset your password:</p>
            <p style="margin: 30px 0;">
                <a href="{reset_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    Reset Password
                </a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #666;">{reset_url}</p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request a password reset, you can safely ignore this email.</p>
        </body>
        </html>
        """

        return await EmailService.send_email(
            to_email=to_email,
            subject=f"Reset your {settings.APP_NAME} password",
            html_content=html_content,
        )

    @staticmethod
    async def send_email_change_confirmation(
        new_email: str, token: str, base_url: str = "http://localhost:8000"
    ) -> bool:
        """
        Send a confirmation link to the NEW email address for an email change request.

        Args:
            new_email: The new email address the user wants to switch to
            token: Email change confirmation token
            base_url: Base URL of the application

        Returns:
            True if email sent successfully
        """
        confirm_url = f"{base_url}/api/v1/auth/confirm-email-change?token={token}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Confirm Your New Email Address</h2>
            <p>Someone requested to change their {settings.APP_NAME} account email to this address.</p>
            <p>Click the button below to confirm and complete the change:</p>
            <p style="margin: 30px 0;">
                <a href="{confirm_url}"
                   style="background-color: #059669; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    Confirm Email Change
                </a>
            </p>
            <p>Or copy and paste this link:</p>
            <p style="word-break: break-all; color: #666;">{confirm_url}</p>
            <p>This link will expire in 24 hours.</p>
            <p>If you did not request this, you can safely ignore this email.</p>
        </body>
        </html>
        """

        return await EmailService.send_email(
            to_email=new_email,
            subject=f"Confirm your new {settings.APP_NAME} email address",
            html_content=html_content,
        )

    @staticmethod
    async def send_otp_email(
        to_email: str, code: str, base_url: str = "http://localhost:8000"
    ) -> bool:
        """
        Send a one-time password (OTP) code for passwordless login.

        Args:
            to_email: Recipient email address
            code: 6-digit OTP code
            base_url: Base URL (unused but kept for API consistency)

        Returns:
            True if email sent successfully
        """
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Your One-Time Login Code</h2>
            <p>Use the code below to sign in to your {settings.APP_NAME} account:</p>
            <div style="margin: 30px 0; text-align: center;">
                <div style="font-size: 48px; font-weight: bold; letter-spacing: 12px;
                            color: #4F46E5; background: #EEF2FF; padding: 20px 40px;
                            border-radius: 8px; display: inline-block;">
                    {code}
                </div>
            </div>
            <p>This code is valid for <strong>10 minutes</strong>.</p>
            <p>If you did not request this code, you can safely ignore this email.</p>
        </body>
        </html>
        """

        return await EmailService.send_email(
            to_email=to_email,
            subject=f"Your {settings.APP_NAME} login code: {code}",
            html_content=html_content,
        )
