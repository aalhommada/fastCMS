"""
Security utilities for password hashing and JWT token management.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context with bcrypt (cost factor 10 for compatibility)
# Lower rounds to avoid initialization issues with some bcrypt versions
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=10,
    bcrypt__ident="2b",  # Use 2b identifier for better compatibility
)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Bcrypt has a 72-byte limit, so we truncate to ensure compatibility.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    # Bcrypt has a max length of 72 bytes - truncate the string (not bytes)
    # Passlib expects a string, not bytes
    password_truncated = password[:72]
    return pwd_context.hash(password_truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password.

    Bcrypt has a 72-byte limit, so we truncate to ensure compatibility.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    # Bcrypt has a max length of 72 bytes - truncate the string (not bytes)
    # Passlib expects a string, not bytes
    password_truncated = plain_password[:72]
    return pwd_context.verify(password_truncated, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of data to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token with unique jti.

    Args:
        data: Dictionary of data to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    # Add unique jti (JWT ID) to prevent token collisions
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string to decode

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def validate_password_policy(password: str) -> list[str]:
    """
    Validate password against configured policy settings.

    Args:
        password: Plain text password to validate

    Returns:
        List of validation error messages (empty = password is valid)
    """
    errors: list[str] = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long")

    if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    if settings.PASSWORD_REQUIRE_SPECIAL and not any(
        c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password
    ):
        errors.append("Password must contain at least one special character (!@#$%^&*...)")

    return errors


def create_impersonation_token(user_id: str, impersonator_id: str, duration_seconds: int = 3600) -> str:
    """
    Create a short-lived impersonation token for a user (admin only).
    The token is non-renewable — no refresh token is issued.

    Args:
        user_id: The user being impersonated
        impersonator_id: The admin performing the impersonation
        duration_seconds: How long the token is valid (default 1 hour)

    Returns:
        Encoded JWT access token with impersonation flag
    """
    expire = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    payload = {
        "sub": user_id,
        "impersonated": True,
        "impersonated_by": impersonator_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def generate_file_token(user_id: str, file_id: str, duration_seconds: int = 120) -> str:
    """
    Generate a short-lived JWT for protected file access.

    Args:
        user_id: User requesting access
        file_id: The file to grant access to
        duration_seconds: Token lifetime (default 2 minutes)

    Returns:
        Signed JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    payload = {
        "sub": user_id,
        "file_id": file_id,
        "type": "file_access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_file_token(token: str, file_id: str) -> Optional[str]:
    """
    Verify a file access token and return the user_id on success.

    Args:
        token: JWT token string
        file_id: File ID that must match the token's file_id claim

    Returns:
        user_id if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "file_access":
            return None
        if payload.get("file_id") != file_id:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def verify_token_type(payload: Dict[str, Any], expected_type: str) -> bool:
    """
    Verify that a token payload has the expected type.

    Args:
        payload: Decoded token payload
        expected_type: Expected token type ('access' or 'refresh')

    Returns:
        True if token type matches, False otherwise
    """
    return payload.get("type") == expected_type
