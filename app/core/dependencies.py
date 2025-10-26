"""
FastAPI dependencies for dependency injection.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token, verify_token_type
from app.db.session import get_db


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Get current authenticated user ID from JWT token.

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        User ID from token or None if not authenticated

    Raises:
        UnauthorizedException: If token is invalid
    """
    if not authorization:
        return None

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None

        payload = decode_token(token)
        if not payload:
            raise UnauthorizedException("Invalid or expired token")

        if not verify_token_type(payload, "access"):
            raise UnauthorizedException("Invalid token type")

        user_id: str = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid token payload")

        return user_id

    except ValueError:
        return None


async def require_auth(
    user_id: Optional[str] = Depends(get_current_user_id),
) -> str:
    """
    Dependency that requires authentication.

    Args:
        user_id: User ID from get_current_user_id dependency

    Returns:
        User ID

    Raises:
        UnauthorizedException: If user is not authenticated
    """
    if not user_id:
        raise UnauthorizedException("Authentication required")
    return user_id


async def get_optional_user_id(
    user_id: Optional[str] = Depends(get_current_user_id),
) -> Optional[str]:
    """
    Get user ID if authenticated, otherwise None.
    Useful for endpoints that work with or without auth.

    Args:
        user_id: User ID from get_current_user_id dependency

    Returns:
        User ID or None
    """
    return user_id
