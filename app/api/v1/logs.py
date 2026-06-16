"""Logs API endpoints"""
from typing import Optional
from app.utils.timeutils import utcnow
from datetime import timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import require_admin
from app.services.log_service import LogService

router = APIRouter()


@router.get("/logs", dependencies=[Depends(require_admin)])
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    method: Optional[str] = None,
    status: Optional[int] = None,
    user_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get request logs (admin only)"""
    service = LogService(db)

    from_date = utcnow() - timedelta(days=days)

    logs = await service.get_logs(
        limit=limit,
        offset=offset,
        method=method,
        status_code=status,
        user_id=user_id,
        from_date=from_date,
    )

    return {
        "items": [
            {
                "id": log.id,
                "method": log.method,
                "url": log.url,
                "status": log.status_code,
                "duration_ms": log.duration_ms,
                "ip_address": log.ip_address,
                "user_id": log.auth_user_id,
                "created": log.created.isoformat(),
            }
            for log in logs
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/logs/statistics", dependencies=[Depends(require_admin)])
async def get_statistics(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get log statistics (admin only)"""
    service = LogService(db)
    from_date = utcnow() - timedelta(days=days)

    stats = await service.get_statistics(from_date=from_date)
    return stats


@router.post("/logs/cleanup", dependencies=[Depends(require_admin)])
async def cleanup_logs(
    retention_days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Cleanup old logs (admin only)"""
    service = LogService(db)
    deleted = await service.cleanup_old_logs(retention_days)
    return {"deleted": deleted}
