"""
FastCMS SDK exception hierarchy.
"""


class FastCMSError(Exception):
    """Base exception for all FastCMS SDK errors."""

    def __init__(self, message: str, status: int | None = None, data: dict | None = None):
        super().__init__(message)
        self.status = status
        self.data = data


class AuthError(FastCMSError):
    """Raised on authentication / authorization failures (401, 403)."""


class ValidationError(FastCMSError):
    """Raised when the server returns 422 Unprocessable Entity."""

    def __init__(self, message: str, fields: dict | None = None):
        super().__init__(message, status=422, data=fields)
        self.fields = fields


class NotFoundError(FastCMSError):
    """Raised when a requested resource is not found (404)."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status=404)


class NetworkError(FastCMSError):
    """Raised on connection / transport failures."""
