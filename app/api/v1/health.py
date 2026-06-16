"""Enhanced health check endpoint"""
import os
from app.utils.timeutils import utcnow
import psutil
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings
from app.core.readonly import is_readonly, get_readonly_reason

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "readonly": is_readonly(),
    }


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check with system info"""
    health = {
        "status": "healthy",
        "timestamp": utcnow().isoformat(),
        "service": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        },
        "readonly": {
            "enabled": is_readonly(),
            "reason": get_readonly_reason(),
        },
    }

    # Database check
    try:
        result = await db.execute(text("SELECT 1"))
        result.fetchone()
        health["database"] = {"status": "connected", "type": "SQLite" if "sqlite" in settings.DATABASE_URL else "PostgreSQL"}
    except Exception as e:
        health["database"] = {"status": "error", "error": str(e)}
        health["status"] = "unhealthy"

    # System resources
    try:
        health["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }
    except Exception:
        health["system"] = {"error": "Unable to get system metrics"}

    # Storage
    try:
        data_dir = "./data"
        if os.path.exists(data_dir):
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(data_dir)
                for filename in filenames
            )
            health["storage"] = {
                "data_dir_size_mb": round(total_size / 1024 / 1024, 2),
                "type": settings.STORAGE_TYPE if hasattr(settings, "STORAGE_TYPE") else "local",
            }
    except Exception:
        health["storage"] = {"error": "Unable to get storage info"}

    return health
