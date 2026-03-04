"""
Plugin settings service — async CRUD + synchronous startup loader.
"""
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.plugin_setting import PluginSetting
from app.db.session import AsyncSessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_plugin_settings(db: AsyncSession, plugin_id: str) -> dict[str, Any]:
    """Return {key: value} for all settings belonging to plugin_id."""
    rows = await db.execute(
        select(PluginSetting).where(PluginSetting.plugin_id == plugin_id)
    )
    return {row.key: row.get_value() for row in rows.scalars().all()}


async def set_plugin_setting(
    db: AsyncSession, plugin_id: str, key: str, value: Any
) -> None:
    """Upsert a single plugin setting (insert or update by primary key)."""
    result = await db.execute(
        select(PluginSetting).where(
            PluginSetting.plugin_id == plugin_id,
            PluginSetting.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PluginSetting(plugin_id=plugin_id, key=key)
        db.add(row)
    row.set_value(value)
    await db.flush()


async def update_plugin_settings(
    db: AsyncSession, plugin_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Bulk update multiple settings for a plugin. Returns updated settings dict."""
    for key, value in data.items():
        await set_plugin_setting(db, plugin_id, key, value)
    await db.commit()
    return await get_plugin_settings(db, plugin_id)


async def get_all_plugin_settings() -> dict[str, dict[str, Any]]:
    """
    Load all plugin settings grouped by plugin_id.
    Returns {plugin_id: {key: value}}.
    Used at startup before the request lifecycle begins.
    """
    async with AsyncSessionLocal() as db:
        rows = await db.execute(select(PluginSetting))
        result: dict[str, dict[str, Any]] = {}
        for row in rows.scalars().all():
            result.setdefault(row.plugin_id, {})[row.key] = row.get_value()
        return result


