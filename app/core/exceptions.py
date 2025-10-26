"""
Custom exception classes for the application.
"""

from typing import Any, Dict, Optional


class FastCMSException(Exception):
    """Base exception class for FastCMS."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundException(FastCMSException):
    """Exception raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=404, details=details)


class UnauthorizedException(FastCMSException):
    """Exception raised when authentication fails."""

    def __init__(self, message: str = "Unauthorized", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=401, details=details)


class ForbiddenException(FastCMSException):
    """Exception raised when user doesn't have permission."""

    def __init__(self, message: str = "Forbidden", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=403, details=details)


class BadRequestException(FastCMSException):
    """Exception raised when request data is invalid."""

    def __init__(self, message: str = "Bad request", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=400, details=details)


class ConflictException(FastCMSException):
    """Exception raised when there's a conflict (e.g., duplicate resource)."""

    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=409, details=details)


class ValidationException(FastCMSException):
    """Exception raised when data validation fails."""

    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=422, details=details)


class TooManyRequestsException(FastCMSException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str = "Too many requests", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=429, details=details)


class DatabaseException(FastCMSException):
    """Exception raised when database operation fails."""

    def __init__(self, message: str = "Database error", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=500, details=details)


class FileStorageException(FastCMSException):
    """Exception raised when file storage operation fails."""

    def __init__(self, message: str = "File storage error", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=500, details=details)


class AIServiceException(FastCMSException):
    """Exception raised when AI service operation fails."""

    def __init__(self, message: str = "AI service error", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=500, details=details)
