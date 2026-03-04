"""
Unit tests for EmailService.

All tests mock _sync_send so no real SMTP connection is needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def smtp_configured(monkeypatch):
    """Make SMTP appear configured for all tests unless overridden."""
    monkeypatch.setattr("app.core.config.settings.SMTP_USER", "test@example.com")
    monkeypatch.setattr("app.core.config.settings.SMTP_PASSWORD", "secret")
    monkeypatch.setattr("app.core.config.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.core.config.settings.SMTP_PORT", 587)
    monkeypatch.setattr("app.core.config.settings.SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr("app.core.config.settings.SMTP_FROM_NAME", "TestApp")
    monkeypatch.setattr("app.core.config.settings.APP_NAME", "TestApp")
    monkeypatch.setattr("app.core.config.settings.BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Core send tests
# ---------------------------------------------------------------------------

class TestSendEmail:

    @pytest.mark.asyncio
    async def test_send_email_calls_sync_send(self):
        """send_email should delegate to _sync_send via thread executor."""
        with patch("app.services.email_service._sync_send", return_value=True) as mock_fn, \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock(return_value=True)
            mock_loop.return_value.run_in_executor = mock_executor

            from app.services.email_service import EmailService
            result = await EmailService.send_email(
                "user@test.com", "Subject", "<p>body</p>", "plain body"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_email_returns_false_when_smtp_not_configured(self, monkeypatch):
        """Returns False immediately when SMTP is not set up."""
        monkeypatch.setattr("app.core.config.settings.SMTP_USER", "")
        monkeypatch.setattr("app.core.config.settings.SMTP_PASSWORD", "")

        from app.services.email_service import EmailService
        result = await EmailService.send_email("user@test.com", "S", "<p>b</p>")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_email_auto_generates_plain_text(self):
        """When plain_content is empty, a fallback is generated."""
        with patch("app.services.email_service._sync_send", return_value=True) as mock_fn, \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=True)

            from app.services.email_service import EmailService
            await EmailService.send_email("u@x.com", "Test Subject", "<p>html</p>", "")
            # The executor was called, meaning plain_content was generated rather than failing
            mock_loop.return_value.run_in_executor.assert_called_once()


# ---------------------------------------------------------------------------
# _sync_send unit test
# ---------------------------------------------------------------------------

class TestSyncSend:

    def test_sync_send_returns_false_on_exception(self):
        """_sync_send returns False when SMTP raises."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = ConnectionRefusedError("refused")
            from app.services.email_service import _sync_send
            result = _sync_send("x@y.com", "S", "<p>b</p>", "plain")
            assert result is False

    def test_sync_send_returns_true_on_success(self):
        """_sync_send returns True when SMTP succeeds."""
        with patch("smtplib.SMTP") as mock_smtp:
            ctx = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=ctx)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            from app.services.email_service import _sync_send
            result = _sync_send("x@y.com", "S", "<p>b</p>", "plain")
            assert result is True


# ---------------------------------------------------------------------------
# HTML template helper
# ---------------------------------------------------------------------------

class TestHtmlWrap:

    def test_html_wrap_contains_title(self):
        from app.services.email_service import _html_wrap
        html = _html_wrap(title="Hello World", body="some body text")
        assert "Hello World" in html

    def test_html_wrap_includes_cta(self):
        from app.services.email_service import _html_wrap
        html = _html_wrap("T", "B", cta_url="https://example.com", cta_label="Click Me")
        assert "https://example.com" in html
        assert "Click Me" in html

    def test_html_wrap_no_cta_when_not_provided(self):
        from app.services.email_service import _html_wrap
        html = _html_wrap("T", "B")
        assert "Click Me" not in html

    def test_plain_text_includes_title_and_url(self):
        from app.services.email_service import _plain_text
        text = _plain_text("Reset Password", "Click below.", "https://example.com/reset")
        assert "Reset Password" in text
        assert "https://example.com/reset" in text


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

class TestGenerateToken:

    def test_generate_token_returns_string(self):
        from app.services.email_service import EmailService
        token = EmailService.generate_token()
        assert isinstance(token, str)

    def test_generate_token_is_unique(self):
        from app.services.email_service import EmailService
        tokens = {EmailService.generate_token() for _ in range(20)}
        assert len(tokens) == 20  # all unique

    def test_generate_token_length(self):
        from app.services.email_service import EmailService
        token = EmailService.generate_token()
        assert len(token) >= 32


# ---------------------------------------------------------------------------
# Specific email type tests
# ---------------------------------------------------------------------------

class TestVerificationEmail:

    @pytest.mark.asyncio
    async def test_sends_with_correct_subject(self):
        with patch.object(__import__("app.services.email_service",
                                     fromlist=["EmailService"]).EmailService,
                          "send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            from app.services.email_service import EmailService
            await EmailService.send_verification_email("u@x.com", "abc123")
            call_args = mock_send.call_args
            subject = call_args[0][1] if call_args[0] else call_args[1]["subject"]
            assert "verify" in subject.lower() or "TestApp" in subject

    @pytest.mark.asyncio
    async def test_verification_url_in_body(self):
        captured_html = []
        async def capture(*args, **kwargs):
            captured_html.append(args[2] if len(args) > 2 else kwargs.get("html_content", ""))
            return True

        with patch("app.services.email_service.EmailService.send_email", side_effect=capture):
            from app.services.email_service import EmailService
            await EmailService.send_verification_email("u@x.com", "TOK123")
            assert "TOK123" in captured_html[0]


class TestPasswordResetEmail:

    @pytest.mark.asyncio
    async def test_reset_url_contains_token(self):
        captured = []
        async def capture(*args, **kwargs):
            captured.append(args)
            return True

        with patch("app.services.email_service.EmailService.send_email", side_effect=capture):
            from app.services.email_service import EmailService
            await EmailService.send_password_reset_email("u@x.com", "RESETTOKEN")
            html = captured[0][2]
            assert "RESETTOKEN" in html


class TestSecurityNotifications:

    @pytest.mark.asyncio
    async def test_login_notification_includes_ip(self):
        captured = []
        async def capture(*args, **kwargs):
            captured.append(args)
            return True

        with patch("app.services.email_service.EmailService.send_email", side_effect=capture):
            from app.services.email_service import EmailService
            await EmailService.send_login_notification(
                "u@x.com", "192.168.1.1", "Mozilla/5.0", "http://localhost"
            )
            html = captured[0][2]
            assert "192.168.1.1" in html

    @pytest.mark.asyncio
    async def test_password_changed_notification_includes_ip(self):
        captured = []
        async def capture(*args, **kwargs):
            captured.append(args)
            return True

        with patch("app.services.email_service.EmailService.send_email", side_effect=capture):
            from app.services.email_service import EmailService
            await EmailService.send_password_changed_notification(
                "u@x.com", "10.0.0.1"
            )
            html = captured[0][2]
            assert "10.0.0.1" in html

    @pytest.mark.asyncio
    async def test_account_locked_notification_includes_duration(self):
        captured = []
        async def capture(*args, **kwargs):
            captured.append(args)
            return True

        with patch("app.services.email_service.EmailService.send_email", side_effect=capture):
            from app.services.email_service import EmailService
            await EmailService.send_account_locked_notification("u@x.com", 30)
            html = captured[0][2]
            assert "30" in html

    @pytest.mark.asyncio
    async def test_2fa_enabled_notification_subject(self):
        subjects = []
        async def capture(to, subject, *args, **kwargs):
            subjects.append(subject)
            return True

        with patch("app.services.email_service.EmailService.send_email", side_effect=capture):
            from app.services.email_service import EmailService
            await EmailService.send_2fa_enabled_notification("u@x.com")
            assert any("2fa" in s.lower() or "two-factor" in s.lower() for s in subjects)

    @pytest.mark.asyncio
    async def test_2fa_disabled_notification_subject(self):
        subjects = []
        async def capture(to, subject, *args, **kwargs):
            subjects.append(subject)
            return True

        with patch("app.services.email_service.EmailService.send_email", side_effect=capture):
            from app.services.email_service import EmailService
            await EmailService.send_2fa_disabled_notification("u@x.com")
            assert any("2fa" in s.lower() or "two-factor" in s.lower() for s in subjects)
