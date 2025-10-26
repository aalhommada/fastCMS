"""
API endpoints for authentication.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_auth
from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    PasswordChange,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter()


def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """
    Extract client information from request.

    Args:
        request: FastAPI request

    Returns:
        Tuple of (user_agent, ip_address)
    """
    user_agent = request.headers.get("user-agent")
    # Get real IP from proxy headers if behind reverse proxy
    ip_address = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or request.headers.get("x-real-ip")
        or request.client.host if request.client else None
    )
    return user_agent, ip_address


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password.",
)
async def register(
    data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Register a new user.

    Args:
        data: Registration data
        request: Request object
        db: Database session

    Returns:
        Auth response with user and tokens
    """
    service = AuthService(db)
    user_agent, ip_address = get_client_info(request)
    return await service.register(data, user_agent, ip_address)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
    description="Authenticate user and receive access and refresh tokens.",
)
async def login(
    data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Login user.

    Args:
        data: Login credentials
        request: Request object
        db: Database session

    Returns:
        Auth response with user and tokens
    """
    service = AuthService(db)
    user_agent, ip_address = get_client_info(request)
    return await service.login(data, user_agent, ip_address)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using a refresh token.",
)
async def refresh_tokens(
    data: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Refresh access token.

    Args:
        data: Refresh token
        request: Request object
        db: Database session

    Returns:
        New token response
    """
    service = AuthService(db)
    user_agent, ip_address = get_client_info(request)
    return await service.refresh_tokens(data.refresh_token, user_agent, ip_address)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user",
    description="Revoke the current refresh token.",
)
async def logout(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Logout user.

    Args:
        data: Refresh token to revoke
        db: Database session
    """
    service = AuthService(db)
    await service.logout(data.refresh_token)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout from all devices",
    description="Revoke all refresh tokens for the authenticated user. Requires authentication.",
)
async def logout_all(
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Logout user from all devices.

    Args:
        user_id: Authenticated user ID
        db: Database session
    """
    service = AuthService(db)
    await service.logout_all(user_id)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the authenticated user's profile. Requires authentication.",
)
async def get_current_user(
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Get current user profile.

    Args:
        user_id: Authenticated user ID
        db: Database session

    Returns:
        User response
    """
    service = AuthService(db)
    return await service.get_user(user_id)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
    description="Update the authenticated user's profile. Requires authentication.",
)
async def update_current_user(
    data: UserUpdate,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update current user profile.

    Args:
        data: Update data
        user_id: Authenticated user ID
        db: Database session

    Returns:
        Updated user response
    """
    service = AuthService(db)
    return await service.update_user(user_id, data)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description="Change the authenticated user's password. Requires authentication.",
)
async def change_password(
    data: PasswordChange,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Change user password.

    Args:
        data: Password change data
        user_id: Authenticated user ID
        db: Database session
    """
    service = AuthService(db)
    await service.change_password(user_id, data)
