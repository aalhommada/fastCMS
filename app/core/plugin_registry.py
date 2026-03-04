"""
Plugin registry — global singleton tracking loaded plugins and their admin UI extensions.
"""
from dataclasses import dataclass, field


@dataclass
class PluginMeta:
    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""


@dataclass
class AdminPage:
    nav_id: str
    label: str
    icon: str
    url: str
    plugin_id: str


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[PluginMeta] = []
        self._admin_pages: list[AdminPage] = []
        self._plugin_ids: set[str] = set()

    def register_plugin(self, meta: PluginMeta) -> None:
        if meta.id in self._plugin_ids:
            # Replace existing registration (allows reload in dev)
            self._plugins = [p for p in self._plugins if p.id != meta.id]
        self._plugins.append(meta)
        self._plugin_ids.add(meta.id)

    def get_plugins(self) -> list[PluginMeta]:
        return list(self._plugins)

    def add_admin_page(self, page: AdminPage) -> None:
        # Deduplicate by nav_id
        self._admin_pages = [p for p in self._admin_pages if p.nav_id != page.nav_id]
        self._admin_pages.append(page)

    def get_admin_pages(self) -> list[AdminPage]:
        return list(self._admin_pages)

    def clear(self) -> None:
        """Reset registry — used in tests."""
        self._plugins.clear()
        self._admin_pages.clear()
        self._plugin_ids.clear()


_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    return _registry
