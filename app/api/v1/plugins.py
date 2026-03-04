"""
Admin REST endpoints for the plugin system.

Provides plugin listing and settings management for administrators.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import UserContext, require_admin
from app.core.plugin_registry import get_registry
from app.db.session import get_db
from app.services.plugin_service import get_plugin_settings, update_plugin_settings

router = APIRouter()


@router.get("/plugins", summary="List all loaded plugins")
async def list_plugins(
    user: UserContext = Depends(require_admin),
) -> list[dict[str, str]]:
    """Return metadata for all successfully loaded plugins."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "version": p.version,
            "author": p.author,
            "description": p.description,
        }
        for p in get_registry().get_plugins()
    ]


@router.get("/plugins/{plugin_id}/settings", summary="Get plugin settings")
async def get_settings(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """Return the current settings dict for a plugin."""
    _assert_plugin_exists(plugin_id)
    return await get_plugin_settings(db, plugin_id)


@router.patch("/plugins/{plugin_id}/settings", summary="Update plugin settings")
async def patch_settings(
    plugin_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """Merge the given keys into the plugin's settings. Returns updated settings."""
    _assert_plugin_exists(plugin_id)
    return await update_plugin_settings(db, plugin_id, data)


def _assert_plugin_exists(plugin_id: str) -> None:
    known_ids = {p.id for p in get_registry().get_plugins()}
    if plugin_id not in known_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_id}' not found",
        )
