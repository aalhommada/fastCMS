"""
Admin API for email configuration and testing.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.dependencies import require_admin
from app.core.logging import get_logger
from app.services.email_service import EmailService

logger = get_logger(__name__)

router = APIRouter(prefix="/email", tags=["Admin - Email"])


class EmailStatusResponse(BaseModel):
    smtp_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str          # masked
    smtp_from_email: str
    smtp_from_name: str
    security_notifications_enabled: bool
    security_login_notifications: bool


class TestEmailRequest(BaseModel):
    to_email: EmailStr


class TestEmailResponse(BaseModel):
    success: bool
    message: str


@router.get(
    "/status",
    response_model=EmailStatusResponse,
    summary="Get email configuration status",
)
async def get_email_status(
    _: str = Depends(require_admin),
) -> EmailStatusResponse:
    """Return current SMTP configuration (password masked)."""
    masked_user = (
        settings.SMTP_USER[:3] + "****" + settings.SMTP_USER[-3:]
        if len(settings.SMTP_USER) > 6 else ("****" if settings.SMTP_USER else "")
    )
    return EmailStatusResponse(
        smtp_enabled=settings.SMTP_ENABLED,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_user=masked_user,
        smtp_from_email=settings.SMTP_FROM_EMAIL,
        smtp_from_name=settings.SMTP_FROM_NAME,
        security_notifications_enabled=settings.SECURITY_NOTIFICATIONS_ENABLED,
        security_login_notifications=settings.SECURITY_LOGIN_NOTIFICATIONS,
    )


@router.post(
    "/test",
    response_model=TestEmailResponse,
    summary="Send a test email",
)
async def send_test_email(
    body: TestEmailRequest,
    _: str = Depends(require_admin),
) -> TestEmailResponse:
    """
    Send a test email to verify SMTP configuration is working.
    Requires SMTP to be configured in environment variables.
    """
    if not settings.SMTP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP is not configured. Set SMTP_USER and SMTP_PASSWORD in your environment.",
        )

    from app.services.email_service import _html_wrap, _plain_text

    html = _html_wrap(
        title="Test email — SMTP is working!",
        body=f"This is a test email from your <strong>{settings.APP_NAME}</strong> instance.<br><br>"
             f"If you received this, your SMTP configuration is correct.<br><br>"
             f"<strong>Configuration:</strong><br>"
             f"Host: <code>{settings.SMTP_HOST}:{settings.SMTP_PORT}</code><br>"
             f"From: <code>{settings.SMTP_FROM_EMAIL}</code>",
    )
    plain = _plain_text(
        "Test email — SMTP is working!",
        f"This is a test email from {settings.APP_NAME}.\n\n"
        f"SMTP Host: {settings.SMTP_HOST}:{settings.SMTP_PORT}\n"
        f"From: {settings.SMTP_FROM_EMAIL}",
    )

    success = await EmailService.send_email(
        to_email=str(body.to_email),
        subject=f"[{settings.APP_NAME}] Test email",
        html_content=html,
        plain_content=plain,
    )

    if success:
        logger.info(f"Test email sent to {body.to_email}")
        return TestEmailResponse(success=True, message=f"Test email sent to {body.to_email}")

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Failed to send test email. Check SMTP credentials and server logs.",
    )
