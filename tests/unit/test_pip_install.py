"""
Tests for pip-installable FastCMS package.

Verifies that the CLI entry point, bundled resources, and init command
work correctly for both source-mode and pip-installed mode.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli.entry import cli


class TestCliEntryPoint:
    """Test the unified CLI entry point."""

    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "FastCMS Command Line Interface" in result.output

    def test_cli_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "FastCMS CLI" in result.output

    def test_cli_has_all_commands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        expected_commands = [
            "create-admin",
            "create-collection",
            "create-user",
            "delete-collection",
            "dev",
            "info",
            "init",
            "list-collections",
            "list-users",
            "migrate",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in CLI help"


class TestBundledResources:
    """Test the bundled resource locator."""

    def test_get_migrations_dir_source_mode(self):
        from app._bundled import get_migrations_dir

        migrations_dir = get_migrations_dir()
        assert migrations_dir.exists()
        assert (migrations_dir / "env.py").exists()
        assert (migrations_dir / "versions").is_dir()

    def test_get_alembic_ini_source_mode(self):
        from app._bundled import get_alembic_ini

        alembic_ini = get_alembic_ini()
        assert alembic_ini.exists()
        assert alembic_ini.name == "alembic.ini"

    def test_migrations_have_version_files(self):
        from app._bundled import get_migrations_dir

        versions_dir = get_migrations_dir() / "versions"
        py_files = list(versions_dir.glob("*.py"))
        assert len(py_files) >= 10, f"Expected at least 10 migration files, got {len(py_files)}"


class TestInitCommand:
    """Test the init command scaffolding."""

    def test_init_creates_project(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_path = Path(tmpdir) / project_name

            with runner.isolated_filesystem(temp_dir=tmpdir):
                os.chdir(tmpdir)
                result = runner.invoke(cli, ["init", project_name])
                assert result.exit_code == 0
                assert "Success" in result.output

                # Check project structure
                assert project_path.exists()
                assert (project_path / ".env").exists()
                assert (project_path / ".gitignore").exists()
                assert (project_path / "README.md").exists()
                assert (project_path / "alembic.ini").exists()
                assert (project_path / "data").is_dir()
                assert (project_path / "data" / "files").is_dir()
                assert (project_path / "plugins").is_dir()
                assert (project_path / "hooks").is_dir()
                assert (project_path / "migrations").is_dir()
                assert (project_path / "migrations" / "env.py").exists()
                assert (project_path / "migrations" / "versions").is_dir()

    def test_init_generates_secret_key(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_path = Path(tmpdir) / project_name

            with runner.isolated_filesystem(temp_dir=tmpdir):
                os.chdir(tmpdir)
                result = runner.invoke(cli, ["init", project_name])
                assert result.exit_code == 0

                env_content = (project_path / ".env").read_text()
                # Should NOT have the placeholder key
                assert "your-secret-key-here" not in env_content
                # Should have a hex key (64 chars for token_hex(32))
                for line in env_content.splitlines():
                    if line.startswith("SECRET_KEY="):
                        key = line.split("=", 1)[1]
                        assert len(key) == 64, f"SECRET_KEY should be 64 hex chars, got {len(key)}"
                        break

    def test_init_copies_migrations(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_path = Path(tmpdir) / project_name

            with runner.isolated_filesystem(temp_dir=tmpdir):
                os.chdir(tmpdir)
                result = runner.invoke(cli, ["init", project_name])
                assert result.exit_code == 0

                versions_dir = project_path / "migrations" / "versions"
                py_files = list(versions_dir.glob("*.py"))
                assert len(py_files) >= 10

    def test_init_rejects_existing_directory(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_path = Path(tmpdir) / project_name
            project_path.mkdir()

            with runner.isolated_filesystem(temp_dir=tmpdir):
                os.chdir(tmpdir)
                result = runner.invoke(cli, ["init", project_name])
                assert "already exists" in result.output

    def test_init_postgres_database_url(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_path = Path(tmpdir) / project_name

            with runner.isolated_filesystem(temp_dir=tmpdir):
                os.chdir(tmpdir)
                result = runner.invoke(cli, ["init", project_name, "--database", "postgres"])
                assert result.exit_code == 0

                env_content = (project_path / ".env").read_text()
                assert "postgresql+asyncpg" in env_content


class TestMigrateCommand:
    """Test the migrate command helpers."""

    def test_get_alembic_ini_local_first(self):
        """When alembic.ini exists locally, use it."""
        from cli.commands.migrate import _get_alembic_ini

        with tempfile.TemporaryDirectory() as tmpdir:
            ini_path = Path(tmpdir) / "alembic.ini"
            ini_path.write_text("[alembic]\n")
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _get_alembic_ini()
                assert result == "alembic.ini"
            finally:
                os.chdir(orig_cwd)

    def test_get_alembic_ini_fallback_to_bundled(self):
        """When no local alembic.ini, fall back to bundled."""
        from cli.commands.migrate import _get_alembic_ini

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _get_alembic_ini()
                assert "alembic.ini" in result
                assert Path(result).exists()
            finally:
                os.chdir(orig_cwd)
