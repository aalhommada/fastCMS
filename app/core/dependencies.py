"""
FastAPI dependencies for dependency injection.
"""

from dataclasses import dataclass, field
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token, verify_token_type
from app.db.session import get_db


@dataclass
class UserContext:
    """User context for authenticated requests."""

    user_id: str
    role: str = "user"
    auth_type: str = "jwt"  # "jwt" or "api_key"
    api_key_id: Optional[str] = None
    api_key_scopes: Optional[str] = None
    email: Optional[str] = None


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserContext]:
    """
    Get current authenticated user context from JWT token or API key.
    Checks: X-API-Key header, Authorization header, access_token cookie.

    Args:
        request: FastAPI request object
        authorization: Authorization header with Bearer token
        x_api_key: X-API-Key header for API key auth
        access_token: JWT token from cookie
        db: Database session

    Returns:
        UserContext with user_id and role, or None if not authenticated
    """
    # Check API Key first (for service-to-service auth)
    if x_api_key:
        return await _validate_api_key(x_api_key, request, db)

    # Check JWT token
    token = None

    # Check Authorization header
    if authorization:
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                token = None
        except ValueError:
            token = None

    # Fall back to cookie if no header token
    if not token and access_token:
        token = access_token

    # No token found anywhere
    if not token:
        return None

    try:
        payload = decode_token(token)
        if not payload:
            raise UnauthorizedException("Invalid or expired token")

        if not verify_token_type(payload, "access"):
            raise UnauthorizedException("Invalid token type")

        user_id: str = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid token payload")

        # Fetch user role from database
        from app.db.repositories.user import UserRepository

        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise UnauthorizedException("User not found")

        return UserContext(user_id=user_id, role=user.role, auth_type="jwt", email=user.email)

    except (ValueError, UnauthorizedException):
        return None


async def _validate_api_key(
    api_key: str,
    request: Request,
    db: AsyncSession,
) -> Optional[UserContext]:
    """
    Validate an API key and return UserContext.

    Args:
        api_key: The API key string
        request: FastAPI request object
        db: Database session

    Returns:
        UserContext if valid, None otherwise
    """
    try:
        from app.services.api_key_service import APIKeyService
        from app.db.repositories.user import UserRepository

        service = APIKeyService(db)
        ip_address = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or request.headers.get("x-real-ip")
            or (request.client.host if request.client else None)
        )

        result = await service.validate_key(api_key, ip_address)

        # Get user role
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(result["user_id"])

        if not user:
            return None

        return UserContext(
            user_id=result["user_id"],
            role=user.role,
            auth_type="api_key",
            api_key_id=result["key_id"],
            api_key_scopes=result["scopes"],
        )

    except Exception:
        return None


async def get_current_user_id(
    user_context: Optional[UserContext] = Depends(get_current_user),
) -> Optional[str]:
    """
    Get current authenticated user ID (backward compatibility).

    Args:
        user_context: User context from get_current_user dependency

    Returns:
        User ID from token or None if not authenticated
    """
    return user_context.user_id if user_context else None


async def require_auth_context(
    user_context: Optional[UserContext] = Depends(get_current_user),
) -> UserContext:
    """
    Dependency that requires authentication and returns UserContext.

    Args:
        user_context: User context from get_current_user dependency

    Returns:
        UserContext with user_id and role

    Raises:
        UnauthorizedException: If user is not authenticated
    """
    if not user_context:
        raise UnauthorizedException("Authentication required")
    return user_context


async def require_auth(
    user_context: Optional[UserContext] = Depends(get_current_user),
) -> str:
    """
    Dependency that requires authentication and returns user ID.
    For backward compatibility with existing endpoints.

    Args:
        user_context: User context from get_current_user dependency

    Returns:
        User ID string

    Raises:
        UnauthorizedException: If user is not authenticated
    """
    if not user_context:
        raise UnauthorizedException("Authentication required")
    return user_context.user_id


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


async def get_optional_user(
    user_context: Optional[UserContext] = Depends(get_current_user),
) -> Optional[UserContext]:
    """
    Get user context if authenticated, otherwise None.

    Args:
        user_context: User context from get_current_user dependency

    Returns:
        UserContext or None
    """
    return user_context


async def require_admin(
    user_context: UserContext = Depends(require_auth_context),
) -> UserContext:
    """
    Dependency that requires admin role.

    Args:
        user_context: User context from require_auth dependency

    Returns:
        UserContext

    Raises:
        UnauthorizedException: If user is not admin
    """
    if user_context.role != "admin":
        raise ForbiddenException("Admin access required")
    return user_context
