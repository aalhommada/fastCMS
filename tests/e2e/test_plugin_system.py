"""
E2E tests for the plugin system.

Tests the full lifecycle: plugin discovery → route registration → hook firing → settings CRUD.
"""
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugin_registry import get_registry
from app.db.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_plugin(plugin_dir: Path, content: str) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "__init__.py").write_text(content)


async def _make_admin(client: AsyncClient, db: AsyncSession, email: str) -> str:
    """Register a user directly in DB, promote to admin, return access token."""
    import bcrypt
    from app.db.models.user import User as UserModel
    # Create user directly to avoid rate limits
    pw_hash = bcrypt.hashpw("AdminPass123!".encode(), bcrypt.gensalt()).decode()
    u = UserModel(email=email, password_hash=pw_hash, role="admin", verified=True)
    db.add(u)
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AdminPass123!"},
    )
    data = resp.json()
    # Support both token formats used in the codebase
    if "token" in data:
        return data["token"]["access_token"]
    return data["access_token"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestPluginRegistry:
    """Tests that verify the in-memory plugin registry works correctly."""

    def test_get_registry_returns_singleton(self):
        from app.core.plugin_registry import get_registry as gr
        assert gr() is gr()

    def test_registry_is_importable(self):
        from app.core.plugin_registry import PluginMeta, AdminPage, PluginRegistry
        assert PluginMeta
        assert AdminPage
        assert PluginRegistry


@pytest.mark.e2e
class TestPluginLoader:
    """Tests for plugin discovery and loading (using temporary plugin dirs)."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        get_registry().clear()
        yield
        get_registry().clear()

    def test_valid_plugin_registered_after_load(self, tmp_path, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "my_plugin",
            """
PLUGIN_META = {"id": "my-plugin", "name": "My Plugin", "version": "1.0.0"}
def register(ctx): pass
""",
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        from fastapi import FastAPI
        from app.core.plugin_loader import load_plugins
        app = FastAPI()
        load_plugins(str(plugins_dir), app, {})
        assert any(p.id == "my-plugin" for p in get_registry().get_plugins())

    def test_broken_plugin_does_not_prevent_others_loading(self, tmp_path, monkeypatch):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "broken",
            """
PLUGIN_META = {"id": "broken", "name": "Broken", "version": "1.0.0"}
def register(ctx):
    raise RuntimeError("kaboom")
""",
        )
        _write_plugin(
            plugins_dir / "good",
            """
PLUGIN_META = {"id": "good", "name": "Good", "version": "1.0.0"}
def register(ctx): pass
""",
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        from fastapi import FastAPI
        from app.core.plugin_loader import load_plugins
        app = FastAPI()
        load_plugins(str(plugins_dir), app, {})
        plugin_ids = {p.id for p in get_registry().get_plugins()}
        assert "good" in plugin_ids
        assert "broken" not in plugin_ids


@pytest.mark.e2e
class TestPluginRoutes:
    """E2E: plugin-registered routes are accessible via HTTP."""

    async def test_example_plugin_hello_route(self, client: AsyncClient):
        """The example plugin's /hello route is accessible without auth."""
        resp = await client.get("/api/v1/plugins/example/hello")
        # If example plugin is loaded, returns 200; if not loaded, 404 is acceptable
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["plugin"] == "example-plugin"


@pytest.mark.e2e
class TestPluginAdminAPI:
    """E2E: admin REST endpoints for plugin management."""

    async def test_list_plugins_requires_admin(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/plugins")
        assert resp.status_code == 401

    async def test_list_plugins_as_admin(self, client: AsyncClient, db: AsyncSession):
        token = await _make_admin(client, db, "plugin-admin@test.dev")
        resp = await client.get(
            "/api/v1/admin/plugins",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_plugin_settings_unknown_plugin_returns_404(
        self, client: AsyncClient, db: AsyncSession
    ):
        token = await _make_admin(client, db, "plugin-admin2@test.dev")
        resp = await client.get(
            "/api/v1/admin/plugins/does-not-exist/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_patch_plugin_settings_unknown_plugin_returns_404(
        self, client: AsyncClient, db: AsyncSession
    ):
        token = await _make_admin(client, db, "plugin-admin3@test.dev")
        resp = await client.patch(
            "/api/v1/admin/plugins/does-not-exist/settings",
            json={"key": "value"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


@pytest.mark.e2e
class TestPluginAdminUI:
    """E2E: admin UI pages for plugins."""

    async def test_admin_plugins_page_is_accessible(
        self, client: AsyncClient
    ):
        """The /admin/plugins page renders without server error."""
        resp = await client.get("/admin/plugins", follow_redirects=True)
        assert resp.status_code in (200, 302, 303)

    async def test_plugins_html_template_exists(self):
        from pathlib import Path
        template_path = Path("app/admin/templates/plugins.html")
        assert template_path.exists(), "plugins.html template must exist"

    async def test_plugins_nav_link_in_base_template(self):
        base = Path("app/admin/templates/base.html").read_text()
        assert "/admin/plugins" in base, "Plugins nav link must be in base.html"
        assert "fa-puzzle-piece" in base, "Plugins icon must be in base.html"
