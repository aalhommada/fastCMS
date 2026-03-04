"""
Unit tests for the plugin registry.
"""
import pytest
from app.core.plugin_registry import AdminPage, PluginMeta, PluginRegistry


class TestPluginRegistry:

    def setup_method(self):
        self.registry = PluginRegistry()

    def test_starts_empty(self):
        assert self.registry.get_plugins() == []
        assert self.registry.get_admin_pages() == []

    def test_register_plugin(self):
        meta = PluginMeta(id="my-plugin", name="My Plugin", version="1.0.0")
        self.registry.register_plugin(meta)
        plugins = self.registry.get_plugins()
        assert len(plugins) == 1
        assert plugins[0].id == "my-plugin"
        assert plugins[0].name == "My Plugin"
        assert plugins[0].version == "1.0.0"

    def test_register_multiple_plugins(self):
        self.registry.register_plugin(PluginMeta(id="a", name="A", version="1.0.0"))
        self.registry.register_plugin(PluginMeta(id="b", name="B", version="2.0.0"))
        assert len(self.registry.get_plugins()) == 2

    def test_duplicate_plugin_id_replaces(self):
        self.registry.register_plugin(PluginMeta(id="same", name="Old", version="1.0.0"))
        self.registry.register_plugin(PluginMeta(id="same", name="New", version="2.0.0"))
        plugins = self.registry.get_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "New"
        assert plugins[0].version == "2.0.0"

    def test_add_admin_page(self):
        page = AdminPage(
            nav_id="my-page", label="My Page", icon="fa-star", url="/admin/my-page",
            plugin_id="my-plugin"
        )
        self.registry.add_admin_page(page)
        pages = self.registry.get_admin_pages()
        assert len(pages) == 1
        assert pages[0].nav_id == "my-page"
        assert pages[0].url == "/admin/my-page"

    def test_duplicate_admin_page_nav_id_replaces(self):
        page1 = AdminPage(nav_id="same", label="Old", icon="fa-a", url="/old", plugin_id="p1")
        page2 = AdminPage(nav_id="same", label="New", icon="fa-b", url="/new", plugin_id="p2")
        self.registry.add_admin_page(page1)
        self.registry.add_admin_page(page2)
        pages = self.registry.get_admin_pages()
        assert len(pages) == 1
        assert pages[0].label == "New"

    def test_clear_resets_state(self):
        self.registry.register_plugin(PluginMeta(id="x", name="X", version="1.0.0"))
        self.registry.add_admin_page(
            AdminPage(nav_id="x", label="X", icon="fa-x", url="/x", plugin_id="x")
        )
        self.registry.clear()
        assert self.registry.get_plugins() == []
        assert self.registry.get_admin_pages() == []

    def test_get_plugins_returns_copy(self):
        self.registry.register_plugin(PluginMeta(id="a", name="A", version="1.0.0"))
        result = self.registry.get_plugins()
        result.clear()  # Should not affect registry
        assert len(self.registry.get_plugins()) == 1

    def test_plugin_meta_optional_fields(self):
        meta = PluginMeta(id="min", name="Minimal", version="0.1.0")
        assert meta.author == ""
        assert meta.description == ""
