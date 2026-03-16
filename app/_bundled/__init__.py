"""
Bundled resources helper.

Locates migrations and alembic.ini regardless of whether FastCMS
is running from source (git clone) or installed via pip.
"""

from pathlib import Path

_BUNDLED_DIR = Path(__file__).parent


def get_migrations_dir() -> Path:
    """Return path to migrations directory.

    Prefers repo-root migrations/ (source/editable-install mode)
    over the bundled copy inside the wheel.
    """
    # Source mode: migrations/ at the repo root
    source_root = _BUNDLED_DIR.parent.parent
    source_migrations = source_root / "migrations"
    if source_migrations.exists() and (source_migrations / "env.py").exists():
        return source_migrations
    # Pip-installed mode: bundled inside the package
    bundled = _BUNDLED_DIR / "migrations"
    if bundled.exists():
        return bundled
    raise FileNotFoundError(
        "Cannot find migrations directory. "
        "Run 'fastcms init <project>' to scaffold a project, or reinstall fastcms."
    )


def get_alembic_ini() -> Path:
    """Return path to alembic.ini.

    Prefers repo-root alembic.ini (source/editable-install mode)
    over the bundled copy inside the wheel.
    """
    # Source mode
    source_root = _BUNDLED_DIR.parent.parent
    source_ini = source_root / "alembic.ini"
    if source_ini.exists():
        return source_ini
    # Pip-installed mode
    bundled = _BUNDLED_DIR / "alembic.ini"
    if bundled.exists():
        return bundled
    raise FileNotFoundError(
        "Cannot find alembic.ini. "
        "Run 'fastcms init <project>' to scaffold a project, or reinstall fastcms."
    )
