"""
Plugin loader — discovers and loads plugin packages from the plugins/ directory at startup.

Each plugin package must have:
  - __init__.py with a PLUGIN_META dict and a register(ctx: PluginContext) function

Example plugin structure:
  plugins/
    my_plugin/
      __init__.py    # PLUGIN_META + register(ctx)
      routes.py      # Optional FastAPI router
      models.py      # Optional SQLAlchemy models (inherit Base)
      hooks.py       # Optional async event handlers
      templates/     # Optional Jinja2 templates
"""

import importlib.util
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.core.plugin_registry import PluginMeta, get_registry
from app.fastcms_plugin_api import PluginContext

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_logger(__name__)

_REQUIRED_META_KEYS = {"id", "name", "version"}
_loaded_plugins: list[dict] = []  # [{id, name, version}]


def load_plugins(
    plugins_dir: str,
    app: "FastAPI",
    plugin_settings: dict[str, dict],
) -> None:
    """
    Scan plugins_dir for Python packages and load each one.

    Called once during application lifespan startup after init_db().
    A plugin that fails to load is skipped — it never crashes the server.

    Args:
        plugins_dir: Path to the plugins directory (e.g. "./plugins")
        app: The FastAPI application instance
        plugin_settings: Pre-loaded settings per plugin {plugin_id: {key: value}}
    """
    plugins_path = Path(plugins_dir)
    if not plugins_path.exists():
        logger.debug(f"Plugins directory '{plugins_dir}' not found — skipping plugin loading")
        return

    packages = sorted(
        p for p in plugins_path.iterdir()
        if p.is_dir() and (p / "__init__.py").exists() and not p.name.startswith("_")
    )

    if not packages:
        logger.debug(f"No plugin packages found in '{plugins_dir}'")
        return

    for pkg_dir in packages:
        _load_single_plugin(pkg_dir, plugins_path, app, plugin_settings)


def _load_single_plugin(
    pkg_dir: Path,
    plugins_path: Path,
    app: "FastAPI",
    plugin_settings: dict[str, dict],
) -> None:
    """Load one plugin package. Errors are caught and logged."""
    module_name = f"fastcms_plugin.{pkg_dir.name}"
    init_file = pkg_dir / "__init__.py"
    try:
        # Import via spec so we don't need plugins/ to be a Python package
        if module_name in sys.modules:
            module = sys.modules[module_name]
        else:
            spec = importlib.util.spec_from_file_location(module_name, init_file,
                submodule_search_locations=[str(pkg_dir)])
            if spec is None or spec.loader is None:
                logger.warning(f"Could not create spec for plugin '{pkg_dir.name}'")
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Validate PLUGIN_META
        meta_data = getattr(module, "PLUGIN_META", None)
        if not isinstance(meta_data, dict):
            logger.warning(
                f"Plugin '{pkg_dir.name}' has no PLUGIN_META dict — skipping"
            )
            return

        missing = _REQUIRED_META_KEYS - meta_data.keys()
        if missing:
            logger.warning(
                f"Plugin '{pkg_dir.name}' PLUGIN_META missing keys {missing} — skipping"
            )
            return

        meta = PluginMeta(
            id=meta_data["id"],
            name=meta_data["name"],
            version=meta_data["version"],
            author=meta_data.get("author", ""),
            description=meta_data.get("description", ""),
        )

        # Validate register() callable
        register_fn = getattr(module, "register", None)
        if not callable(register_fn):
            logger.warning(
                f"Plugin '{meta.name}' has no register() function — skipping"
            )
            return

        # Build context and call register()
        ctx = PluginContext(
            plugin_id=meta.id,
            app=app,
            settings=plugin_settings.get(meta.id, {}),
        )
        register_fn(ctx)

        # Record in registry
        get_registry().register_plugin(meta)
        _loaded_plugins.append({"id": meta.id, "name": meta.name, "version": meta.version})
        logger.info(f"Plugin loaded: {meta.name} v{meta.version} [{meta.id}]")

    except Exception:
        logger.error(
            f"Failed to load plugin '{pkg_dir.name}':\n{traceback.format_exc()}"
        )


def get_loaded_plugins() -> list[dict]:
    """Return metadata for all successfully loaded plugins."""
    return list(_loaded_plugins)
