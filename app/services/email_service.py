"""
Email service for sending transactional and security emails via SMTP.

SMTP is inherently blocking (smtplib), so we run it in a thread-pool executor
to avoid blocking the async event loop.
"""

import asyncio
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _html_wrap(title: str, body: str, cta_url: Optional[str] = None,
               cta_label: Optional[str] = None) -> str:
    """
    Wrap email body in a consistent branded HTML shell.

    Uses table-based layout for maximum email client compatibility.
    """
    cta_block = ""
    if cta_url and cta_label:
        cta_block = f"""
        <tr>
          <td style="padding:24px 0 8px;">
            <a href="{cta_url}"
               style="background:#4F46E5;color:#fff;padding:12px 28px;
                      text-decoration:none;border-radius:6px;font-size:15px;
                      font-weight:600;display:inline-block;">
              {cta_label}
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding:12px 0 0;font-size:13px;color:#6B7280;">
            Or copy this link into your browser:<br>
            <span style="word-break:break-all;color:#4F46E5;">{cta_url}</span>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F9FAFB;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0"
               style="background:#fff;border-radius:12px;border:1px solid #E5E7EB;overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="background:#4F46E5;padding:24px 32px;">
              <span style="color:#fff;font-size:20px;font-weight:700;">{settings.APP_NAME}</span>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <h2 style="margin:0 0 16px;font-size:22px;color:#111827;">{title}</h2>
                  </td>
                </tr>
                <tr>
                  <td style="font-size:15px;color:#374151;line-height:1.6;">
                    {body}
                  </td>
                </tr>
                {cta_block}
              </table>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background:#F9FAFB;padding:20px 32px;border-top:1px solid #E5E7EB;">
              <p style="margin:0;font-size:12px;color:#9CA3AF;text-align:center;">
                {settings.APP_NAME} &bull; This is an automated message, please do not reply.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _plain_text(title: str, body_plain: str, cta_url: Optional[str] = None) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    lines = [settings.APP_NAME, "=" * len(settings.APP_NAME), "", title, "-" * len(title), "",
             body_plain]
    if cta_url:
        lines += ["", cta_url]
    lines += ["", f"— {settings.APP_NAME} (automated message)"]
    return "\n".join(lines)


def _sync_send(to_email: str, subject: str, html_content: str,
               plain_content: str) -> bool:
    """
    Synchronous SMTP send — runs in a thread-pool executor.
    Returns True on success, False on failure (always logs the error).
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(plain_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as exc:
        logger.error(f"SMTP send to {to_email} failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class EmailService:
    """High-level email sending service. All public methods are async-safe."""

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def generate_token() -> str:
        """Generate a cryptographically secure URL-safe token."""
        return secrets.token_urlsafe(32)

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    @staticmethod
    async def send_email(to_email: str, subject: str, html_content: str,
                         plain_content: str = "") -> bool:
        """
        Send an email asynchronously (SMTP runs in a thread-pool executor).

        Args:
            to_email: Recipient address
            subject: Email subject line
            html_content: Full HTML body
            plain_content: Optional plain-text fallback (auto-generated if empty)

        Returns:
            True on success, False on failure.
        """
        if not settings.SMTP_ENABLED:
            logger.warning(f"SMTP not configured — email to {to_email} not sent")
            return False

        if not plain_content:
            plain_content = f"{subject}\n\n{settings.APP_NAME}"

        loop = asyncio.get_event_loop()
        fn = partial(_sync_send, to_email, subject, html_content, plain_content)
        result: bool = await loop.run_in_executor(None, fn)

        if result:
            logger.info(f"Email sent: '{subject}' → {to_email}")
        return result

    # ------------------------------------------------------------------
    # Transactional emails
    # ------------------------------------------------------------------

    @staticmethod
    async def send_verification_email(to_email: str, verification_token: str,
                                      base_url: str = "") -> bool:
        base_url = base_url or settings.BASE_URL
        url = f"{base_url}/api/v1/auth/verify-email?token={verification_token}"

        html = _html_wrap(
            title="Verify your email address",
            body=f"Thanks for signing up to <strong>{settings.APP_NAME}</strong>!<br><br>"
                 f"Click the button below to verify your email address. "
                 f"This link expires in <strong>24 hours</strong>.<br><br>"
                 f"If you didn't create an account, you can safely ignore this email.",
            cta_url=url,
            cta_label="Verify Email Address",
        )
        plain = _plain_text(
            "Verify your email address",
            f"Thanks for signing up to {settings.APP_NAME}!\n\n"
            f"Click the link below to verify your email address.\n"
            f"This link expires in 24 hours.\n\n"
            f"If you didn't create an account, ignore this email.",
            url,
        )
        return await EmailService.send_email(
            to_email, f"Verify your {settings.APP_NAME} account", html, plain)

    @staticmethod
    async def send_password_reset_email(to_email: str, reset_token: str,
                                        base_url: str = "") -> bool:
        base_url = base_url or settings.BASE_URL
        url = f"{base_url}/auth/reset-password?token={reset_token}"

        html = _html_wrap(
            title="Reset your password",
            body=f"We received a request to reset the password for your "
                 f"<strong>{settings.APP_NAME}</strong> account.<br><br>"
                 f"Click the button below to set a new password. "
                 f"This link expires in <strong>1 hour</strong>.<br><br>"
                 f"If you didn't request this, you can safely ignore this email. "
                 f"Your password won't change until you click the link.",
            cta_url=url,
            cta_label="Reset Password",
        )
        plain = _plain_text(
            "Reset your password",
            f"We received a request to reset your {settings.APP_NAME} password.\n\n"
            f"Click the link below to reset it. This link expires in 1 hour.\n\n"
            f"If you didn't request this, ignore this email.",
            url,
        )
        return await EmailService.send_email(
            to_email, f"Reset your {settings.APP_NAME} password", html, plain)

    @staticmethod
    async def send_email_change_confirmation(new_email: str, token: str,
                                             base_url: str = "") -> bool:
        base_url = base_url or settings.BASE_URL
        url = f"{base_url}/api/v1/auth/confirm-email-change?token={token}"

        html = _html_wrap(
            title="Confirm your new email address",
            body=f"Someone requested to change their <strong>{settings.APP_NAME}</strong> "
                 f"account email to this address.<br><br>"
                 f"Click the button below to confirm and complete the change. "
                 f"This link expires in <strong>24 hours</strong>.<br><br>"
                 f"If you did not request this, ignore this email.",
            cta_url=url,
            cta_label="Confirm Email Change",
        )
        plain = _plain_text(
            "Confirm your new email address",
            f"Someone requested to change their {settings.APP_NAME} account email to this address.\n\n"
            f"Click the link below to confirm. This link expires in 24 hours.\n\n"
            f"If you did not request this, ignore this email.",
            url,
        )
        return await EmailService.send_email(
            new_email, f"Confirm your new {settings.APP_NAME} email address", html, plain)

    @staticmethod
    async def send_otp_email(to_email: str, code: str, base_url: str = "") -> bool:
        html = _html_wrap(
            title="Your one-time login code",
            body=f"Use the code below to sign in to your <strong>{settings.APP_NAME}</strong> account:<br><br>"
                 f"<div style='text-align:center;margin:24px 0;'>"
                 f"<span style='font-size:40px;font-weight:700;letter-spacing:10px;"
                 f"color:#4F46E5;background:#EEF2FF;padding:16px 32px;"
                 f"border-radius:8px;display:inline-block;'>{code}</span>"
                 f"</div>"
                 f"This code is valid for <strong>10 minutes</strong>.<br><br>"
                 f"If you didn't request this code, ignore this email.",
        )
        plain = _plain_text(
            "Your one-time login code",
            f"Your {settings.APP_NAME} login code: {code}\n\nValid for 10 minutes.",
        )
        return await EmailService.send_email(
            to_email, f"Your {settings.APP_NAME} login code: {code}", html, plain)

    # ------------------------------------------------------------------
    # Security notification emails
    # ------------------------------------------------------------------

    @staticmethod
    async def send_login_notification(to_email: str, ip_address: str,
                                      user_agent: str, base_url: str = "") -> bool:
        """Send an alert when a new login is detected from an unfamiliar location."""
        base_url = base_url or settings.BASE_URL
        html = _html_wrap(
            title="New sign-in to your account",
            body=f"We detected a new sign-in to your <strong>{settings.APP_NAME}</strong> account.<br><br>"
                 f"<table style='width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;'>"
                 f"<tr style='background:#F9FAFB;'>"
                 f"<td style='padding:10px 14px;border:1px solid #E5E7EB;font-weight:600;width:40%;'>IP Address</td>"
                 f"<td style='padding:10px 14px;border:1px solid #E5E7EB;font-family:monospace;'>{ip_address}</td>"
                 f"</tr>"
                 f"<tr>"
                 f"<td style='padding:10px 14px;border:1px solid #E5E7EB;font-weight:600;'>Device</td>"
                 f"<td style='padding:10px 14px;border:1px solid #E5E7EB;font-family:monospace;'>{user_agent[:80] or 'Unknown'}</td>"
                 f"</tr>"
                 f"</table>"
                 f"If this was you, no action is needed.<br><br>"
                 f"If you don't recognise this activity, change your password immediately.",
            cta_url=f"{base_url}/auth/change-password",
            cta_label="Secure My Account",
        )
        plain = _plain_text(
            "New sign-in to your account",
            f"New sign-in to your {settings.APP_NAME} account.\n\n"
            f"IP Address: {ip_address}\nDevice: {user_agent[:80] or 'Unknown'}\n\n"
            f"If this wasn't you, change your password immediately.",
            f"{base_url}/auth/change-password",
        )
        return await EmailService.send_email(
            to_email,
            f"New sign-in to your {settings.APP_NAME} account",
            html, plain)

    @staticmethod
    async def send_password_changed_notification(to_email: str,
                                                 ip_address: str,
                                                 base_url: str = "") -> bool:
        """Notify user their password was changed."""
        base_url = base_url or settings.BASE_URL
        html = _html_wrap(
            title="Your password was changed",
            body=f"Your <strong>{settings.APP_NAME}</strong> password was successfully changed.<br><br>"
                 f"<strong>IP Address:</strong> <code>{ip_address}</code><br><br>"
                 f"If you made this change, no action is needed.<br><br>"
                 f"If you didn't change your password, your account may be compromised. "
                 f"Please reset your password immediately.",
            cta_url=f"{base_url}/auth/reset-password",
            cta_label="Reset Password Now",
        )
        plain = _plain_text(
            "Your password was changed",
            f"Your {settings.APP_NAME} password was changed from IP: {ip_address}\n\n"
            f"If you didn't do this, reset your password immediately.",
            f"{base_url}/auth/reset-password",
        )
        return await EmailService.send_email(
            to_email,
            f"Your {settings.APP_NAME} password was changed",
            html, plain)

    @staticmethod
    async def send_2fa_enabled_notification(to_email: str) -> bool:
        """Notify user that 2FA was enabled on their account."""
        html = _html_wrap(
            title="Two-factor authentication enabled",
            body=f"Two-factor authentication (2FA) has been <strong>enabled</strong> on your "
                 f"<strong>{settings.APP_NAME}</strong> account.<br><br>"
                 f"Your account is now more secure. You'll need your authenticator app "
                 f"each time you sign in.<br><br>"
                 f"If you didn't enable 2FA, contact support immediately.",
        )
        plain = _plain_text(
            "Two-factor authentication enabled",
            f"2FA has been enabled on your {settings.APP_NAME} account.\n\n"
            f"If you didn't enable 2FA, contact support immediately.",
        )
        return await EmailService.send_email(
            to_email,
            f"2FA enabled on your {settings.APP_NAME} account",
            html, plain)

    @staticmethod
    async def send_2fa_disabled_notification(to_email: str) -> bool:
        """Notify user that 2FA was disabled on their account."""
        html = _html_wrap(
            title="Two-factor authentication disabled",
            body=f"Two-factor authentication (2FA) has been <strong>disabled</strong> on your "
                 f"<strong>{settings.APP_NAME}</strong> account.<br><br>"
                 f"Your account is now less protected. We recommend keeping 2FA enabled.<br><br>"
                 f"If you didn't disable 2FA, contact support and change your password immediately.",
        )
        plain = _plain_text(
            "Two-factor authentication disabled",
            f"2FA has been disabled on your {settings.APP_NAME} account.\n\n"
            f"If you didn't disable 2FA, change your password immediately.",
        )
        return await EmailService.send_email(
            to_email,
            f"2FA disabled on your {settings.APP_NAME} account",
            html, plain)

    @staticmethod
    async def send_account_locked_notification(to_email: str,
                                               lockout_minutes: int,
                                               base_url: str = "") -> bool:
        """Notify user their account was locked due to failed login attempts."""
        base_url = base_url or settings.BASE_URL
        html = _html_wrap(
            title="Your account has been temporarily locked",
            body=f"Your <strong>{settings.APP_NAME}</strong> account has been temporarily locked "
                 f"due to multiple failed sign-in attempts.<br><br>"
                 f"The lock will be lifted automatically in "
                 f"<strong>{lockout_minutes} minute{'s' if lockout_minutes != 1 else ''}</strong>.<br><br>"
                 f"If this wasn't you, someone may be trying to access your account. "
                 f"Reset your password as soon as the lock expires.",
            cta_url=f"{base_url}/auth/reset-password",
            cta_label="Reset Password",
        )
        plain = _plain_text(
            "Your account has been temporarily locked",
            f"Your {settings.APP_NAME} account is locked for {lockout_minutes} minute(s) "
            f"due to multiple failed login attempts.\n\n"
            f"If this wasn't you, reset your password once the lock expires.",
            f"{base_url}/auth/reset-password",
        )
        return await EmailService.send_email(
            to_email,
            f"Your {settings.APP_NAME} account has been locked",
            html, plain)
