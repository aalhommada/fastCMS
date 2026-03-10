"""Custom middleware"""
import time
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.logging import get_logger
from app.core.readonly import is_readonly, get_readonly_reason
from app.core.config import settings

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        # Get user if authenticated
        user_id = None
        if hasattr(request.state, "user"):
            user_id = request.state.user.id

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log to database (async, don't block response)
        try:
            from app.services.settings_service import SettingsService
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                settings = SettingsService(db)
                log_enabled = await settings.get("logs.enabled", True)

                if log_enabled:
                    from app.services.log_service import LogService

                    log_service = LogService(db)
                    await log_service.create_log(
                        method=request.method,
                        url=str(request.url),
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        user_agent=request.headers.get("user-agent"),
                        ip_address=request.client.host if request.client else None,
                        auth_user_id=user_id,
                    )
        except Exception as e:
            logger.error(f"Failed to log request: {str(e)}")

        # Record metrics
        try:
            from app.core.metrics import metrics
            method = request.method
            status_code = str(response.status_code)
            metrics.inc("fastcms_http_requests_total", labels={"method": method, "status": status_code})
            metrics.observe("fastcms_http_request_duration_ms", duration_ms, labels={"method": method})
            if response.status_code >= 500:
                metrics.inc("fastcms_http_errors_total", labels={"method": method, "status": status_code})
        except Exception:
            pass

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class ReadOnlyMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce read-only mode"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if read-only mode is enabled
        if is_readonly():
            # Allow read operations
            if request.method in ["GET", "HEAD", "OPTIONS"]:
                return await call_next(request)

            # Block write operations
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily read-only",
                    "reason": get_readonly_reason(),
                    "detail": "System is in maintenance mode. Only read operations are allowed.",
                },
            )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: XSS filter (legacy browsers)
    - Strict-Transport-Security: HSTS for HTTPS enforcement
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    - Cache-Control: Security-conscious caching
    """

    def __init__(
        self,
        app,
        content_security_policy: Optional[str] = None,
        permissions_policy: Optional[str] = None,
        hsts_max_age: int = 31536000,  # 1 year
        frame_options: str = "DENY",
        include_subdomains: bool = True,
    ):
        super().__init__(app)
        self.csp = content_security_policy or self._default_csp()
        self.permissions = permissions_policy or self._default_permissions()
        self.hsts_max_age = hsts_max_age
        self.frame_options = frame_options
        self.include_subdomains = include_subdomains

    def _default_csp(self) -> str:
        """Default Content Security Policy."""
        return "; ".join([
            "default-src 'self'",
            # Admin UI loads Tailwind, Alpine.js, FontAwesome from CDN
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
            "img-src 'self' data: https:",
            # FontAwesome fonts from cdnjs
            "font-src 'self' data: https://cdnjs.cloudflare.com",
            "connect-src 'self' ws: wss:",  # Allow WebSocket connections
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ])

    def _default_permissions(self) -> str:
        """Default Permissions Policy (formerly Feature-Policy)."""
        return ", ".join([
            "accelerometer=()",
            "camera=()",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "payment=()",
            "usb=()",
        ])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = self.frame_options

        # XSS protection for legacy browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy - send origin only for cross-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy - disable unnecessary browser features
        response.headers["Permissions-Policy"] = self.permissions

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp

        # HSTS - only in production with HTTPS
        if settings.is_production:
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.include_subdomains:
                hsts_value += "; includeSubDomains"
            response.headers["Strict-Transport-Security"] = hsts_value

        # Cache control for API responses
        if request.url.path.startswith("/api/"):
            # Don't cache API responses by default
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
                response.headers["Pragma"] = "no-cache"

        return response


class IPFilterMiddleware(BaseHTTPMiddleware):
    """
    Middleware that checks the client IP against allow/block rules stored in the DB.

    Block rules take precedence.  If no block rules match, the request proceeds.
    Allow rules are purely additive documentation (useful for whitelists in conjunction
    with future IP-restricted API key features).
    """

    # Paths exempt from IP filtering (health checks, etc.)
    EXEMPT_PATHS = {"/health", "/api/v1/health"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip IP filtering if disabled or for exempt paths
        if not settings.IP_FILTER_ENABLED:
            return await call_next(request)

        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Extract client IP
        client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or request.headers.get("x-real-ip")
            or (request.client.host if request.client else None)
        )

        if not client_ip:
            return await call_next(request)

        # Check against rules — requires a DB session
        try:
            from app.db.session import get_async_session
            from app.services.ip_filter_service import IPFilterService

            async with get_async_session() as db:
                svc = IPFilterService(db)
                blocked, reason = await svc.is_blocked(client_ip)

            if blocked:
                logger.warning(f"Blocked IP: {client_ip} — {reason}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Access denied: {reason or 'IP blocked'}"},
                )
        except Exception as e:
            # Don't break the app if IP filter check fails
            logger.error(f"IP filter check failed: {e}")

        return await call_next(request)
