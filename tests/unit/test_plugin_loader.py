"""
Unit tests for the plugin loader.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI

from app.core.plugin_registry import PluginRegistry, get_registry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the global plugin registry before each test."""
    get_registry().clear()
    yield
    get_registry().clear()


@pytest.fixture
def app():
    return FastAPI()


def _write_plugin(plugin_dir: Path, content: str) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "__init__.py").write_text(content)


class TestLoadPlugins:

    def test_no_plugins_dir_is_silent(self, app, tmp_path):
        from app.core.plugin_loader import load_plugins
        load_plugins(str(tmp_path / "nonexistent"), app, {})
        assert get_registry().get_plugins() == []

    def test_empty_plugins_dir_is_silent(self, app, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        assert get_registry().get_plugins() == []

    def test_valid_plugin_is_loaded(self, app, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "good_plugin",
            """
PLUGIN_META = {"id": "good", "name": "Good Plugin", "version": "1.0.0"}
def register(ctx):
    pass
""",
        )
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        plugins = get_registry().get_plugins()
        assert len(plugins) == 1
        assert plugins[0].id == "good"
        assert plugins[0].name == "Good Plugin"

    def test_plugin_without_meta_is_skipped(self, app, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "no_meta",
            "def register(ctx): pass",
        )
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        assert get_registry().get_plugins() == []

    def test_plugin_with_missing_meta_key_is_skipped(self, app, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "bad_meta",
            """
PLUGIN_META = {"id": "x", "name": "X"}  # missing 'version'
def register(ctx): pass
""",
        )
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        assert get_registry().get_plugins() == []

    def test_plugin_without_register_is_skipped(self, app, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "no_register",
            'PLUGIN_META = {"id": "x", "name": "X", "version": "1.0.0"}',
        )
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        assert get_registry().get_plugins() == []

    def test_broken_register_does_not_crash(self, app, tmp_path):
        """A plugin whose register() raises should be skipped, not crash the server."""
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "broken_plugin",
            """
PLUGIN_META = {"id": "broken", "name": "Broken", "version": "1.0.0"}
def register(ctx):
    raise RuntimeError("I am broken")
""",
        )
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        # broken plugin is NOT registered, but no exception propagated
        assert get_registry().get_plugins() == []

    def test_multiple_plugins_all_loaded(self, app, tmp_path):
        plugins_dir = tmp_path / "plugins"
        for i in range(3):
            _write_plugin(
                plugins_dir / f"plugin_{i}",
                f"""
PLUGIN_META = {{"id": "plugin-{i}", "name": "Plugin {i}", "version": "1.0.0"}}
def register(ctx): pass
""",
            )
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        assert len(get_registry().get_plugins()) == 3

    def test_plugin_receives_settings(self, app, tmp_path, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "settings_plugin",
            """
PLUGIN_META = {"id": "settings-test", "name": "Settings", "version": "1.0.0"}
received_setting = None
def register(ctx):
    global received_setting
    received_setting = ctx.get_setting("api_key", "default")
""",
        )
        from app.core.plugin_loader import load_plugins
        load_plugins(
            str(plugins_dir), app,
            plugin_settings={"settings-test": {"api_key": "secret-123"}}
        )
        mod = sys.modules["fastcms_plugin.settings_plugin"]
        assert mod.received_setting == "secret-123"

    def test_plugin_routes_registered_on_app(self, app, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "route_plugin",
            """
PLUGIN_META = {"id": "route-test", "name": "Route Test", "version": "1.0.0"}
from fastapi import APIRouter
_router = APIRouter()
@_router.get("/ping")
async def ping(): return {"pong": True}
def register(ctx):
    ctx.include_router(_router, prefix="/route-test")
""",
        )
        from app.core.plugin_loader import load_plugins
        load_plugins(str(plugins_dir), app, {})
        routes = [r.path for r in app.routes]
        assert any("/api/v1/plugins/route-test/ping" in r for r in routes)
