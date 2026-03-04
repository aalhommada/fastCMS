"""
Authentication endpoints for auth-type collections.
Provides login, register, and password management for auth collections.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user, UserContext
from app.core.security import verify_password, hash_password, create_access_token
from app.db.session import get_db
from app.db.repositories.collection import CollectionRepository
from app.db.models.dynamic import DynamicModelGenerator
from app.schemas.auth import AuthResponse, TokenResponse, UserResponse
from pydantic import BaseModel, EmailStr, Field

router = APIRouter()


class AuthCollectionRegister(BaseModel):
    """Registration schema for auth collections."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: str
    # Additional fields will be added dynamically based on collection schema


class AuthCollectionLogin(BaseModel):
    """Login schema for auth collections."""
    email: EmailStr
    password: str


@router.post("/{collection_name}/auth/register", status_code=201)
async def register_to_auth_collection(
    collection_name: str,
    data: dict,  # Accept any fields from the collection
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user in an auth collection.

    Args:
        collection_name: Name of the auth collection
        data: Registration data including email, password, and custom fields
        request: FastAPI request
        db: Database session

    Returns:
        User data and access token
    """
    # Verify collection exists and is auth type
    collection_repo = CollectionRepository(db)
    collection = await collection_repo.get_by_name(collection_name)

    if not collection:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")

    if collection.type != "auth":
        raise HTTPException(
            status_code=400,
            detail=f"Collection '{collection_name}' is not an auth collection"
        )

    # Validate required fields
    if 'email' not in data or 'password' not in data:
        raise HTTPException(
            status_code=400,
            detail="Email and password are required"
        )

    if 'password_confirm' in data and data['password'] != data['password_confirm']:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Get the dynamic model for this collection
    from app.db.repositories.record import RecordRepository
    record_repo = RecordRepository(db, collection_name)
    model = await record_repo._get_model()

    # Check if email already exists
    result = await db.execute(
        select(model).where(model.email == data['email'])
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Hash the password
    hashed_password = hash_password(data['password'])

    # Prepare record data
    record_data = {k: v for k, v in data.items() if k not in ['password_confirm']}
    record_data['password'] = hashed_password
    record_data['verified'] = False
    record_data['email_visibility'] = data.get('email_visibility', True)

    # Create the record
    new_user = model(**record_data)
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    await db.commit()

    # Generate token
    token_data = {
        "sub": new_user.id,
        "email": new_user.email,
        "collection": collection_name
    }
    access_token = create_access_token(token_data)

    # Prepare response (exclude password)
    user_dict = {
        column.name: getattr(new_user, column.name)
        for column in new_user.__table__.columns
        if column.name != 'password'
    }

    return {
        "user": user_dict,
        "token": {
            "access_token": access_token,
            "token_type": "bearer"
        }
    }


@router.post("/{collection_name}/auth/login")
async def login_to_auth_collection(
    collection_name: str,
    credentials: AuthCollectionLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Login to an auth collection.

    Args:
        collection_name: Name of the auth collection
        credentials: Login credentials (email and password)
        db: Database session

    Returns:
        User data and access token
    """
    # Verify collection exists and is auth type
    collection_repo = CollectionRepository(db)
    collection = await collection_repo.get_by_name(collection_name)

    if not collection:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")

    if collection.type != "auth":
        raise HTTPException(
            status_code=400,
            detail=f"Collection '{collection_name}' is not an auth collection"
        )

    # Get the dynamic model
    from app.db.repositories.record import RecordRepository
    record_repo = RecordRepository(db, collection_name)
    model = await record_repo._get_model()

    # Determine the identity field (default: "email", configurable via collection options)
    identity_field = collection.options.get("identity_field", "email") if collection.options else "email"
    if not hasattr(model, identity_field):
        identity_field = "email"  # Fallback to email if field doesn't exist

    # Find user by identity field
    result = await db.execute(
        select(model).where(getattr(model, identity_field) == credentials.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(
            status_code=401,
            detail=f"Invalid {identity_field} or password"
        )

    # Generate token
    token_data = {
        "sub": user.id,
        "email": user.email,
        "collection": collection_name
    }
    access_token = create_access_token(token_data)

    # Prepare response (exclude password)
    user_dict = {
        column.name: getattr(user, column.name)
        for column in user.__table__.columns
        if column.name != 'password'
    }

    return {
        "user": user_dict,
        "token": {
            "access_token": access_token,
            "token_type": "bearer"
        }
    }


@router.get("/{collection_name}/auth/me")
async def get_current_auth_user(
    collection_name: str,
    db: AsyncSession = Depends(get_db),
    user_context: Optional[UserContext] = Depends(get_current_user),
):
    """
    Get current authenticated user from auth collection.

    Args:
        collection_name: Name of the auth collection
        db: Database session
        user_context: Current user context

    Returns:
        Current user data
    """
    if not user_context:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Get the dynamic model
    from app.db.repositories.record import RecordRepository
    record_repo = RecordRepository(db, collection_name)
    model = await record_repo._get_model()

    # Get user
    result = await db.execute(
        select(model).where(model.id == user_context.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prepare response (exclude password)
    user_dict = {
        column.name: getattr(user, column.name)
        for column in user.__table__.columns
        if column.name != 'password'
    }

    return user_dict


@router.post("/{collection_name}/auth/refresh")
async def refresh_auth_token(
    collection_name: str,
    db: AsyncSession = Depends(get_db),
    user_context: Optional[UserContext] = Depends(get_current_user),
):
    """
    Refresh access token for auth collection user.

    Args:
        collection_name: Name of the auth collection
        db: Database session
        user_context: Current user context

    Returns:
        New access token
    """
    if not user_context:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Verify collection exists and is auth type
    collection_repo = CollectionRepository(db)
    collection = await collection_repo.get_by_name(collection_name)

    if not collection or collection.type != "auth":
        raise HTTPException(status_code=400, detail="Invalid collection")

    # Get the dynamic model
    from app.db.repositories.record import RecordRepository
    record_repo = RecordRepository(db, collection_name)
    model = await record_repo._get_model()

    # Verify user exists
    result = await db.execute(
        select(model).where(model.id == user_context.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate new token
    token_data = {
        "sub": user.id,
        "email": user.email,
        "collection": collection_name
    }
    access_token = create_access_token(token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
