"""
Hook loader — scans and imports user hook scripts from ./hooks/ at startup.

User scripts in hooks/ can use the decorator API:

    from fastcms.hooks import on_record_create, on_record_update, on_record_delete

    @on_record_create("posts")
    async def handle_new_post(event):
        print(f"New post: {event.record}")
"""

import importlib.util
import sys
import traceback
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_loaded_hooks: list[dict] = []  # [{file, module_name, functions}]


def load_hooks(hooks_dir: str = "./hooks") -> None:
    """
    Scan hooks_dir for .py files and import each one.

    Called once at application startup via lifespan.
    """
    hooks_path = Path(hooks_dir)
    if not hooks_path.exists():
        logger.debug(f"Hooks directory '{hooks_dir}' not found — skipping hook loading")
        return

    py_files = sorted(hooks_path.glob("*.py"))
    if not py_files:
        logger.debug(f"No hook files found in '{hooks_dir}'")
        return

    for hook_file in py_files:
        if hook_file.name.startswith("_"):
            continue  # skip __init__.py, etc.

        module_name = f"fastcms_hooks.{hook_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, hook_file)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load hook file: {hook_file}")
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]

            # Collect registered functions from module
            hook_fns = [
                name for name in dir(module)
                if callable(getattr(module, name)) and not name.startswith("_")
            ]

            _loaded_hooks.append({
                "file": str(hook_file),
                "module": module_name,
                "functions": hook_fns,
            })

            logger.info(f"Loaded hook file: {hook_file.name} ({len(hook_fns)} exports)")

        except Exception:
            logger.error(f"Failed to load hook file {hook_file}:\n{traceback.format_exc()}")


def get_loaded_hooks() -> list[dict]:
    """Return metadata about all loaded hook modules."""
    return list(_loaded_hooks)
