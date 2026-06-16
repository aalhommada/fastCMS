"""
Admin API endpoints for managing users, collections, and system.
Requires admin role for all operations.
"""

from typing import Any, Literal, cast
from app.utils.timeutils import utcnow

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import UserContext, require_admin
from app.db.models.collection import Collection
from app.db.models.user import User
from app.db.repositories.collection import CollectionRepository
from app.db.repositories.user import UserRepository
from app.db.session import get_db
from app.schemas.auth import ImpersonationResponse, UserResponse, UserRegister
from app.schemas.collection import CollectionResponse

router = APIRouter()


@router.get("/stats", summary="Get system statistics")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """
    Get system statistics (admin only).

    Returns:
        System statistics including user count, collection count, etc.
    """
    from app.db.models.backup import Backup
    from app.db.models.file import File
    from datetime import timedelta

    user_repo = UserRepository(db)
    collection_repo = CollectionRepository(db)

    # Count users
    total_users = await user_repo.count()

    # Count collections
    total_collections = await collection_repo.count()

    # Count admin users
    result = await db.execute(select(func.count(User.id)).where(User.role == "admin"))
    admin_users = result.scalar_one()

    # Get recent users (last 7 days)
    seven_days_ago = (utcnow() - timedelta(days=7)).isoformat()
    result = await db.execute(
        select(func.count(User.id)).where(User.created >= seven_days_ago)
    )
    recent_users = result.scalar_one()

    # Count backups
    result = await db.execute(select(func.count(Backup.id)))
    total_backups = result.scalar_one()

    # Get recent backups (last 5)
    result = await db.execute(
        select(Backup).order_by(Backup.created.desc()).limit(5)
    )
    recent_backups_list = result.scalars().all()
    recent_backups = [
        {
            "id": b.id,
            "filename": b.filename,
            "size": b.size_bytes,
            "created": b.created.isoformat(),
        }
        for b in recent_backups_list
    ]

    # Count files (exclude thumbnails)
    result = await db.execute(
        select(func.count(File.id)).where(
            File.deleted == False,
            File.is_thumbnail == False
        )
    )
    total_files = result.scalar_one()

    # Sum file sizes (exclude thumbnails)
    result = await db.execute(
        select(func.sum(File.size)).where(
            File.deleted == False,
            File.is_thumbnail == False
        )
    )
    total_file_size = result.scalar_one() or 0

    return {
        "users": {
            "total": total_users,
            "admins": admin_users,
            "recent": recent_users,
        },
        "collections": {
            "total": total_collections,
        },
        "backups": {
            "total": total_backups,
            "recent": recent_backups,
        },
        "files": {
            "total": total_files,
            "total_size": total_file_size,
        },
    }


@router.get("/users", response_model=dict[str, Any], summary="List all users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """
    List all users with pagination (admin only).

    Args:
        page: Page number
        per_page: Items per page
        db: Database session
        _: Admin user context

    Returns:
        Paginated list of users
    """
    user_repo = UserRepository(db)

    skip = (page - 1) * per_page
    users = await user_repo.get_all(skip=skip, limit=per_page)
    total = await user_repo.count()

    import math

    total_pages = math.ceil(total / per_page) if total > 0 else 0

    return {
        "items": [UserResponse.model_validate(user) for user in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@router.post("/users", response_model=UserResponse, status_code=201, summary="Create a new user")
async def create_user(
    data: UserRegister,
    role: str = Query("user", pattern="^(user|admin)$", description="User role"),
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> UserResponse:
    """
    Create a new user with specified role (admin only).

    Args:
        data: User registration data
        role: User role (user or admin)
        db: Database session
        _: Admin user context

    Returns:
        Created user details
    """
    from app.services.auth_service import AuthService
    from app.core.exceptions import ConflictException

    auth_service = AuthService(db)

    # Check if user already exists
    user_repo = UserRepository(db)
    existing_user = await user_repo.get_by_email(data.email)
    if existing_user:
        raise ConflictException("User with this email already exists")

    # Register the user
    response = await auth_service.register(
        data=data,
        user_agent=None,
        ip_address=None,
    )

    # Update role if not default
    if role != "user":
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == response.user.id))
        user_obj = result.scalar_one_or_none()
        if user_obj:
            user_obj.role = role
            user_obj.verified = True  # Admin-created users are auto-verified
            await db.commit()
            await db.refresh(user_obj)
            return UserResponse.model_validate(user_obj)

    return response.user


@router.get("/users/{user_id}", response_model=UserResponse, summary="Get user details")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> UserResponse:
    """
    Get user details by ID (admin only).

    Args:
        user_id: User ID
        db: Database session
        _: Admin user context

    Returns:
        User details
    """
    from app.core.exceptions import NotFoundException

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise NotFoundException(f"User {user_id} not found")

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse, summary="Update user")
async def update_user(
    user_id: str,
    update_data: dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: UserContext = Depends(require_admin),
) -> UserResponse:
    """
    Update user details (admin only).

    Args:
        user_id: User ID
        update_data: Fields to update (name, email, role, verified, password)
        db: Database session
        admin: Admin user context

    Returns:
        Updated user
    """
    from app.core.exceptions import NotFoundException
    from app.core.security import hash_password

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise NotFoundException(f"User {user_id} not found")

    # Update allowed fields
    if "name" in update_data:
        user.name = update_data["name"]
    if "email" in update_data:
        user.email = update_data["email"]
    if "role" in update_data:
        user.role = update_data["role"]
    if "verified" in update_data:
        user.verified = update_data["verified"]
    if "password" in update_data and update_data["password"]:
        user.password_hash = hash_password(update_data["password"])

    await user_repo.update(user)
    await db.commit()

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/role", response_model=UserResponse, summary="Update user role")
async def update_user_role(
    user_id: str,
    role: str = Query(..., pattern="^(user|admin)$"),
    db: AsyncSession = Depends(get_db),
    admin: UserContext = Depends(require_admin),
) -> UserResponse:
    """
    Update user role (admin only).

    Args:
        user_id: User ID
        role: New role (user or admin)
        db: Database session
        admin: Admin user context

    Returns:
        Updated user
    """
    from app.core.exceptions import BadRequestException, NotFoundException

    if admin.user_id == user_id:
        raise BadRequestException("Cannot change your own role")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise NotFoundException(f"User {user_id} not found")

    user.role = role
    await user_repo.update(user)
    await db.commit()

    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=204, summary="Delete user")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: UserContext = Depends(require_admin),
) -> None:
    """
    Delete user (admin only).

    Args:
        user_id: User ID
        db: Database session
        admin: Admin user context
    """
    from app.core.exceptions import BadRequestException, NotFoundException

    if admin.user_id == user_id:
        raise BadRequestException("Cannot delete your own account")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise NotFoundException(f"User {user_id} not found")

    await user_repo.delete(user)
    await db.commit()


@router.post("/users/{user_id}/unlock", response_model=UserResponse, summary="Unlock a locked account")
async def unlock_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> UserResponse:
    """
    Unlock a user account that was locked due to too many failed login attempts (admin only).

    Args:
        user_id: User ID
        db: Database session

    Returns:
        Updated user details
    """
    from app.core.exceptions import NotFoundException

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise NotFoundException(f"User {user_id} not found")

    user.failed_login_attempts = 0
    user.locked_until = None
    await user_repo.update(user)
    await db.commit()

    return UserResponse.model_validate(user)


@router.post(
    "/users/{user_id}/impersonate",
    response_model=ImpersonationResponse,
    summary="Impersonate a user (admin only)",
)
async def impersonate_user(
    user_id: str,
    duration: int = Query(3600, ge=60, le=86400, description="Token lifetime in seconds (60s–24h)"),
    db: AsyncSession = Depends(get_db),
    admin: UserContext = Depends(require_admin),
) -> ImpersonationResponse:
    """
    Generate a short-lived impersonation token for any user (admin only).
    The token is non-renewable — no refresh token is issued.
    Useful for debugging and support.

    Args:
        user_id: The user to impersonate
        duration: Token lifetime in seconds (default 1 hour, max 24 hours)
    """
    from app.core.exceptions import BadRequestException, NotFoundException
    from app.core.security import create_impersonation_token

    if admin.user_id == user_id:
        raise BadRequestException("Cannot impersonate yourself")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise NotFoundException(f"User {user_id} not found")

    token = create_impersonation_token(user_id, admin.user_id, duration)
    return ImpersonationResponse(
        access_token=token,
        expires_in=duration,
        impersonated_user_id=user_id,
    )


@router.get("/users/{user_id}/lock-status", summary="Get account lock status")
async def get_lock_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """
    Get lock status of a user account (admin only).

    Returns:
        Lock status including failed attempts and locked_until timestamp
    """
    from app.core.exceptions import NotFoundException
    from datetime import timezone

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise NotFoundException(f"User {user_id} not found")

    from datetime import datetime
    now = datetime.now(timezone.utc)
    locked_until = user.locked_until
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    is_locked = bool(locked_until and locked_until > now)

    return {
        "user_id": user_id,
        "is_locked": is_locked,
        "failed_login_attempts": user.failed_login_attempts or 0,
        "locked_until": locked_until.isoformat() if locked_until else None,
        "remaining_seconds": max(0, int((locked_until - now).total_seconds())) if is_locked else 0,
    }


@router.get(
    "/collections", response_model=dict[str, Any], summary="List all collections (admin view)"
)
async def list_collections_admin(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """
    List all collections with full details (admin only).

    Args:
        page: Page number
        per_page: Items per page
        db: Database session
        _: Admin user context

    Returns:
        Paginated list of collections
    """
    from app.utils.field_types import FieldSchema

    collection_repo = CollectionRepository(db)

    skip = (page - 1) * per_page
    collections = await collection_repo.get_all(skip=skip, limit=per_page)
    total = await collection_repo.count()

    import math

    total_pages = math.ceil(total / per_page) if total > 0 else 0

    # Convert collections to response format
    items = []
    for col in collections:
        # Extract fields from schema and migrate old formats
        fields = []
        for field_data in col.schema.get("fields", []):
            # Migrate old boolean cascade_delete to new enum format
            if "relation" in field_data and field_data["relation"]:
                relation_data = field_data["relation"]
                if "cascade_delete" in relation_data:
                    cascade_value = relation_data["cascade_delete"]
                    # Convert old boolean format to new enum string
                    if isinstance(cascade_value, bool):
                        relation_data["cascade_delete"] = "cascade" if cascade_value else "restrict"
                    elif cascade_value is None:
                        relation_data["cascade_delete"] = "restrict"

            fields.append(FieldSchema(**field_data))

        items.append(CollectionResponse(
            id=col.id,
            name=col.name,
            type=cast(Literal["base", "auth", "view"], col.type),
            schema=fields,
            options=col.options,
            list_rule=col.list_rule,
            view_rule=col.view_rule,
            create_rule=col.create_rule,
            update_rule=col.update_rule,
            delete_rule=col.delete_rule,
            view_query=col.view_query,
            system=col.system,
            created=col.created,
            updated=col.updated,
        ))

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@router.delete("/collections/{collection_id}", status_code=204, summary="Delete collection")
async def delete_collection_admin(
    collection_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> None:
    """
    Delete a collection (admin only).

    Args:
        collection_id: Collection ID
        db: Database session
        _: Admin user context
    """
    from app.core.exceptions import BadRequestException, NotFoundException

    collection_repo = CollectionRepository(db)
    collection = await collection_repo.get_by_id(collection_id)

    if not collection:
        raise NotFoundException(f"Collection {collection_id} not found")

    if collection.system:
        raise BadRequestException("Cannot delete system collection")

    await collection_repo.delete(collection)
    await db.commit()


# ===== IP Rules (Allowlist / Blocklist) =====

from datetime import datetime
from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional


class IPRuleCreate(_BaseModel):
    cidr: str
    rule_type: str  # "allow" or "block"
    reason: _Optional[str] = None
    expires_at: _Optional[datetime] = None


@router.get("/ip-rules", summary="List IP rules")
async def list_ip_rules(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    rule_type: _Optional[str] = Query(None, pattern="^(allow|block)$"),
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """List all IP allow/block rules (admin only)."""
    from app.services.ip_filter_service import IPFilterService

    svc = IPFilterService(db)
    skip = (page - 1) * per_page
    rules = await svc.get_all_rules(skip=skip, limit=per_page, rule_type=rule_type)
    total = await svc.count_rules(rule_type=rule_type)

    import math
    return {
        "items": [
            {
                "id": r.id,
                "cidr": r.cidr,
                "rule_type": r.rule_type,
                "reason": r.reason,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "created_by": r.created_by,
                "created": r.created.isoformat(),
            }
            for r in rules
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if total > 0 else 0,
    }


@router.post("/ip-rules", status_code=201, summary="Create IP rule")
async def create_ip_rule(
    data: IPRuleCreate,
    db: AsyncSession = Depends(get_db),
    admin: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """Create an IP allow or block rule (admin only)."""
    from app.services.ip_filter_service import IPFilterService

    svc = IPFilterService(db)
    rule = await svc.create_rule(
        cidr=data.cidr,
        rule_type=data.rule_type,
        reason=data.reason,
        expires_at=data.expires_at,
        created_by=admin.user_id,
    )
    return {
        "id": rule.id,
        "cidr": rule.cidr,
        "rule_type": rule.rule_type,
        "reason": rule.reason,
        "expires_at": rule.expires_at.isoformat() if rule.expires_at else None,
        "created": rule.created.isoformat(),
    }


@router.delete("/ip-rules/{rule_id}", status_code=204, summary="Delete IP rule")
async def delete_ip_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(require_admin),
) -> None:
    """Delete an IP rule (admin only)."""
    from app.services.ip_filter_service import IPFilterService

    svc = IPFilterService(db)
    await svc.delete_rule(rule_id)


# ===== Cron Job Management =====

@router.get("/cron", summary="List cron jobs")
async def list_cron_jobs(
    _: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """List all scheduled cron tasks with their status (admin only)."""
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    tasks = scheduler.get_all_tasks()
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/cron/{task_name}/trigger", summary="Manually trigger a cron job")
async def trigger_cron_job(
    task_name: str,
    _: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """Manually trigger a cron job by name (admin only)."""
    from app.core.scheduler import get_scheduler
    from app.core.exceptions import NotFoundException

    scheduler = get_scheduler()
    found = await scheduler.trigger_task(task_name)
    if not found:
        raise NotFoundException(f"Cron job '{task_name}' not found")
    return {"message": f"Task '{task_name}' triggered successfully"}
