"""
Public API for FastCMS plugin packages.

Plugin packages in plugins/ use this module to register routes, hooks, and admin pages:

    # plugins/my_plugin/__init__.py
    PLUGIN_META = {"id": "my-plugin", "name": "My Plugin", "version": "1.0.0"}

    def register(ctx):
        from .routes import router
        ctx.include_router(router, prefix="/my-plugin")
        ctx.on_record_create("posts", handle_post)
        ctx.add_admin_page(nav_id="my-plugin", label="My Plugin",
                           icon="fa-puzzle-piece", url="/admin/plugins/my-plugin")

For simple hooks/ scripts (drop-in .py files), use app.fastcms_hooks_api instead.
"""
from typing import Any, Callable, Optional

from fastapi import APIRouter, FastAPI

from app.core.events import EventType, get_dispatcher
from app.core.logging import get_logger
from app.core.plugin_registry import AdminPage, get_registry

logger = get_logger(__name__)


def _make_hook(event_type: EventType, collection: Optional[str], handler: Callable) -> None:
    """Register a collection-scoped event handler on the global dispatcher."""
    dispatcher = get_dispatcher()

    async def _wrapped(event) -> None:
        if collection and event.collection_name != collection:
            return
        await handler(event)

    dispatcher.on(event_type, _wrapped)
    logger.debug(
        f"Plugin hook: {handler.__name__} → {event_type.value}"
        + (f" [{collection}]" if collection else "")
    )


class PluginContext:
    """
    Passed to each plugin's register() function at startup.
    Provides a clean API to register routes, hooks, and admin UI extensions.
    """

    def __init__(self, plugin_id: str, app: FastAPI, settings: dict) -> None:
        self._plugin_id = plugin_id
        self._app = app
        self._settings = settings

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    def include_router(
        self,
        router: APIRouter,
        *,
        prefix: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """Register a FastAPI router. Routes are mounted under the given prefix."""
        full_prefix = f"/api/v1/plugins{prefix}"
        self._app.include_router(
            router,
            prefix=full_prefix,
            tags=tags or [f"Plugin: {self._plugin_id}"],
        )
        logger.info(f"Plugin '{self._plugin_id}' registered routes at {full_prefix}")

    def on_record_create(self, collection: Optional[str], handler: Callable) -> None:
        """Hook fires after a record is created. Pass None to fire for all collections."""
        _make_hook(EventType.RECORD_CREATED, collection, handler)

    def on_record_update(self, collection: Optional[str], handler: Callable) -> None:
        """Hook fires after a record is updated. Pass None to fire for all collections."""
        _make_hook(EventType.RECORD_UPDATED, collection, handler)

    def on_record_delete(self, collection: Optional[str], handler: Callable) -> None:
        """Hook fires after a record is deleted. Pass None to fire for all collections."""
        _make_hook(EventType.RECORD_DELETED, collection, handler)

    def on_any_event(self, handler: Callable) -> None:
        """Hook fires on every event regardless of type or collection."""
        dispatcher = get_dispatcher()
        for event_type in EventType:
            dispatcher.on(event_type, handler)
        logger.debug(f"Plugin '{self._plugin_id}' registered global hook: {handler.__name__}")

    def add_admin_page(
        self,
        *,
        nav_id: str,
        label: str,
        icon: str,
        url: str,
    ) -> None:
        """Add an entry to the admin sidebar nav for this plugin."""
        get_registry().add_admin_page(
            AdminPage(nav_id=nav_id, label=label, icon=icon, url=url, plugin_id=self._plugin_id)
        )
        logger.debug(f"Plugin '{self._plugin_id}' registered admin page: {label} → {url}")

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Read a plugin setting by key. Settings are loaded from DB at startup."""
        return self._settings.get(key, default)
