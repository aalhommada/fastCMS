"""
Tests for CLI improvements: plugin install/create/list and seed commands.
"""

import json
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from cli.commands.plugin import (
    PLUGIN_REGISTRY,
    create_plugin,
    install_plugin,
    list_plugins,
    plugin,
)
from cli.commands.seed import DEMO_COLLECTIONS, DEMO_RECORDS, _field_to_sql, seed


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_plugins_dir(tmp_path, monkeypatch):
    """Create a temporary plugins directory and cd into tmp_path."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    return plugins_dir


# ─── Plugin Registry Tests ───────────────────────────────────────────────


class TestPluginRegistry:
    def test_registry_has_required_plugins(self):
        assert "ai-core" in PLUGIN_REGISTRY
        assert "ai-vectors" in PLUGIN_REGISTRY
        assert "ai-rag" in PLUGIN_REGISTRY
        assert "ai-agents" in PLUGIN_REGISTRY
        assert "example" in PLUGIN_REGISTRY

    def test_registry_entries_have_required_fields(self):
        for name, entry in PLUGIN_REGISTRY.items():
            assert "dir" in entry, f"'{name}' missing 'dir'"
            assert "description" in entry, f"'{name}' missing 'description'"
            assert "depends" in entry, f"'{name}' missing 'depends'"
            assert isinstance(entry["depends"], list)

    def test_dependencies_reference_valid_plugins(self):
        for name, entry in PLUGIN_REGISTRY.items():
            for dep in entry["depends"]:
                assert dep in PLUGIN_REGISTRY, f"'{name}' depends on unknown plugin '{dep}'"


# ─── Plugin Create Tests ─────────────────────────────────────────────────


class TestPluginCreate:
    def test_create_plugin_scaffold(self, runner, temp_plugins_dir):
        result = runner.invoke(create_plugin, ["my-analytics"])
        assert result.exit_code == 0
        assert "Created plugins/my_analytics/" in result.output

        plugin_dir = temp_plugins_dir / "my_analytics"
        assert plugin_dir.exists()
        assert (plugin_dir / "__init__.py").exists()
        assert (plugin_dir / "routes.py").exists()
        assert (plugin_dir / "requirements.txt").exists()

    def test_create_plugin_init_content(self, runner, temp_plugins_dir):
        runner.invoke(create_plugin, ["blog-tools"])
        init_file = temp_plugins_dir / "blog_tools" / "__init__.py"
        content = init_file.read_text()

        assert 'PLUGIN_META' in content
        assert '"id": "blog-tools"' in content
        assert '"name": "Blog Tools"' in content
        assert 'def register(ctx)' in content
        assert 'include_router' in content
        assert 'add_admin_page' in content

    def test_create_plugin_routes_content(self, runner, temp_plugins_dir):
        runner.invoke(create_plugin, ["blog-tools"])
        routes_file = temp_plugins_dir / "blog_tools" / "routes.py"
        content = routes_file.read_text()

        assert "APIRouter" in content
        assert '@router.get("/status")' in content
        assert '"plugin": "blog-tools"' in content

    def test_create_plugin_already_exists(self, runner, temp_plugins_dir):
        runner.invoke(create_plugin, ["my-plugin"])
        result = runner.invoke(create_plugin, ["my-plugin"])
        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_create_plugin_name_normalization(self, runner, temp_plugins_dir):
        runner.invoke(create_plugin, ["My Cool Plugin"])
        assert (temp_plugins_dir / "my_cool_plugin").exists()


# ─── Plugin List Tests ────────────────────────────────────────────────────


class TestPluginList:
    def test_list_no_plugins(self, runner, temp_plugins_dir):
        result = runner.invoke(list_plugins)
        assert result.exit_code == 0
        assert "not installed" in result.output

    def test_list_with_installed_plugin(self, runner, temp_plugins_dir):
        # Create a fake installed plugin
        plugin_dir = temp_plugins_dir / "ai_core"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("PLUGIN_META = {}")
        result = runner.invoke(list_plugins)
        assert result.exit_code == 0
        assert "installed" in result.output


# ─── Plugin Install Tests ─────────────────────────────────────────────────


class TestPluginInstall:
    def test_install_unknown_plugin(self, runner, temp_plugins_dir):
        result = runner.invoke(install_plugin, ["nonexistent"])
        assert result.exit_code == 0
        assert "Unknown plugin" in result.output
        assert "Available plugins" in result.output

    def test_install_already_exists(self, runner, temp_plugins_dir):
        plugin_dir = temp_plugins_dir / "example_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("")
        result = runner.invoke(install_plugin, ["example"])
        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_install_already_exists_force(self, runner, temp_plugins_dir):
        """Test that --force overwrites existing plugin."""
        plugin_dir = temp_plugins_dir / "example_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("old")

        # Mock the download so we don't hit the network
        with patch("cli.commands.plugin._download_plugin") as mock_dl:
            result = runner.invoke(install_plugin, ["example", "--force"])
            mock_dl.assert_called_once_with("example", force=True)


# ─── Seed Data Definitions Tests ──────────────────────────────────────────


class TestSeedDataDefinitions:
    def test_demo_collections_defined(self):
        names = [c["name"] for c in DEMO_COLLECTIONS]
        assert "posts" in names
        assert "categories" in names
        assert "products" in names

    def test_demo_collections_have_fields(self):
        for coll in DEMO_COLLECTIONS:
            fields = coll["schema"]["fields"]
            assert len(fields) > 0
            for field in fields:
                assert "name" in field
                assert "type" in field

    def test_demo_records_exist_for_all_collections(self):
        for coll in DEMO_COLLECTIONS:
            assert coll["name"] in DEMO_RECORDS
            assert len(DEMO_RECORDS[coll["name"]]) > 0

    def test_demo_records_match_schema(self):
        for coll in DEMO_COLLECTIONS:
            field_names = {f["name"] for f in coll["schema"]["fields"]}
            for record in DEMO_RECORDS[coll["name"]]:
                for key in record:
                    assert key in field_names, (
                        f"Record key '{key}' not in schema for '{coll['name']}'"
                    )

    def test_field_to_sql_mapping(self):
        assert _field_to_sql("text") == "TEXT"
        assert _field_to_sql("number") == "REAL"
        assert _field_to_sql("bool") == "INTEGER"
        assert _field_to_sql("editor") == "TEXT"
        assert _field_to_sql("date") == "TEXT"
        assert _field_to_sql("json") == "TEXT"
        assert _field_to_sql("email") == "TEXT"
        assert _field_to_sql("unknown_type") == "TEXT"


# ─── Seed Command Integration Tests ──────────────────────────────────────


class TestSeedCommand:
    def test_seed_help(self, runner):
        result = runner.invoke(seed, ["--help"])
        assert result.exit_code == 0
        assert "Seed the database" in result.output
        assert "--force" in result.output
