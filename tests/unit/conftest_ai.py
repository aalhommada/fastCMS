"""
Shared setup for AI plugin tests — registers the fastcms_plugin namespace
so plugin modules can import from each other.
"""

import importlib.util
import sys
import types


def ensure_plugin_namespace():
    """Create the fastcms_plugin namespace package in sys.modules."""
    if "fastcms_plugin" not in sys.modules:
        ns = types.ModuleType("fastcms_plugin")
        ns.__path__ = []  # namespace package
        sys.modules["fastcms_plugin"] = ns


def load_plugin(name: str, path: str, search: str):
    """Load a plugin module the same way the plugin loader does."""
    ensure_plugin_namespace()

    module_name = f"fastcms_plugin.{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=[search]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load plugin {name} from {path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    # Set as attr on parent namespace so `from fastcms_plugin.X import ...` works
    setattr(sys.modules["fastcms_plugin"], name, mod)
    spec.loader.exec_module(mod)
    return mod


def load_all_ai_plugins():
    """Load all AI plugins in the correct order."""
    load_plugin("ai_core", "plugins/ai_core/__init__.py", "plugins/ai_core")
    load_plugin("ai_vectors", "plugins/ai_vectors/__init__.py", "plugins/ai_vectors")
    load_plugin("ai_rag", "plugins/ai_rag/__init__.py", "plugins/ai_rag")
    load_plugin("ai_agents", "plugins/ai_agents/__init__.py", "plugins/ai_agents")
