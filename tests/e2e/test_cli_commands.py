"""
E2E tests for CLI commands — plugin create/list.

Note: Seed tests are in unit tests since they require the real database
with existing tables. Plugin create/list can be tested independently.
"""

import importlib.util
import os

import pytest
from click.testing import CliRunner


class TestPluginCreateE2E:
    """Test plugin scaffold creates valid plugin structure."""

    def test_scaffold_produces_loadable_plugin(self, tmp_path):
        """Verify the scaffolded plugin can be imported and has valid metadata."""
        runner = CliRunner()
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            os.makedirs("plugins", exist_ok=True)
            from cli.commands.plugin import create_plugin

            result = runner.invoke(create_plugin, ["test-loadable"])
            assert result.exit_code == 0

            # Verify the plugin can be imported
            init_path = tmp_path / "plugins" / "test_loadable" / "__init__.py"
            assert init_path.exists()

            spec = importlib.util.spec_from_file_location(
                "test_loadable", str(init_path)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            assert hasattr(module, "PLUGIN_META")
            assert hasattr(module, "register")
            assert module.PLUGIN_META["id"] == "test-loadable"
            assert module.PLUGIN_META["version"] == "0.1.0"
        finally:
            os.chdir(original_dir)

    def test_scaffold_routes_importable(self, tmp_path):
        """Verify the scaffolded routes.py has a valid FastAPI router."""
        runner = CliRunner()
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            os.makedirs("plugins", exist_ok=True)
            from cli.commands.plugin import create_plugin

            result = runner.invoke(create_plugin, ["api-test"])
            assert result.exit_code == 0

            routes_path = tmp_path / "plugins" / "api_test" / "routes.py"
            spec = importlib.util.spec_from_file_location(
                "api_test_routes", str(routes_path)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            assert hasattr(module, "router")
        finally:
            os.chdir(original_dir)


class TestPluginListE2E:
    """Test plugin list against real plugins directory."""

    def test_list_shows_installed_plugins(self):
        """Verify plugin list detects installed plugins."""
        runner = CliRunner()
        from cli.commands.plugin import list_plugins

        result = runner.invoke(list_plugins)
        assert result.exit_code == 0
        # The project has plugins installed
        assert "installed" in result.output

    def test_list_shows_registry(self):
        """Verify plugin list shows the available registry."""
        runner = CliRunner()
        from cli.commands.plugin import list_plugins

        result = runner.invoke(list_plugins)
        assert result.exit_code == 0
        assert "ai-core" in result.output
        assert "ai-vectors" in result.output
        assert "ai-rag" in result.output
        assert "ai-agents" in result.output
