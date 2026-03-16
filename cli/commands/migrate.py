"""
Database migration commands
"""
import asyncio
import os
import subprocess
import sys

import click
from rich.console import Console

console = Console()


def _get_alembic_ini() -> str:
    """Resolve alembic.ini path: local file first, then bundled fallback."""
    if os.path.exists("alembic.ini"):
        return "alembic.ini"
    try:
        from app._bundled import get_alembic_ini
        return str(get_alembic_ini())
    except (ImportError, FileNotFoundError):
        return "alembic.ini"  # let alembic raise its own error


def _run_alembic(args: list[str]) -> subprocess.CompletedProcess:
    """Run an alembic command with the resolved config path."""
    ini = _get_alembic_ini()
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", ini] + args,
        capture_output=True,
        text=True,
    )


def _is_fresh_database() -> bool:
    """Check if the database has no tables (fresh install)."""
    try:
        from app.core.config import settings
        from sqlalchemy import create_engine, inspect

        sync_url = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            inspector = inspect(conn)
            tables = inspector.get_table_names()
        engine.dispose()
        return len(tables) == 0
    except Exception:
        return False


def _create_all_tables() -> None:
    """Create all tables from SQLAlchemy models (for fresh databases)."""
    from app.core.config import settings
    from app.db.base import Base
    from app.db.models import (  # noqa: F401
        backup, collection, email_template, file, logs,
        oauth, plugin_setting, search, settings as settings_model,
        user, verification, webhook,
    )
    from sqlalchemy import create_engine

    # Use sync engine for table creation — avoids WAL corruption from
    # async engine not closing cleanly in a subprocess context.
    sync_url = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        if settings.database_is_sqlite:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
        Base.metadata.create_all(bind=conn)
    engine.dispose()


@click.group()
def migrate():
    """Database migration commands"""
    pass


@migrate.command()
def up():
    """Run all pending migrations"""
    console.print("[bold cyan]Running migrations...[/bold cyan]")
    try:
        # For fresh databases, create all tables then stamp to head
        if _is_fresh_database():
            console.print("[dim]Fresh database detected — creating tables...[/dim]")
            _create_all_tables()
            result = _run_alembic(["stamp", "head"])
            if result.returncode == 0:
                console.print("[green]v[/green] Database initialized and stamped to latest migration")
            else:
                console.print("[red]Error stamping database:[/red]")
                console.print(result.stderr)
            return

        result = _run_alembic(["upgrade", "head"])
        if result.returncode == 0:
            console.print("[green]v[/green] Migrations completed successfully")
            if result.stdout:
                console.print(result.stdout)
        else:
            console.print("[red]Error running migrations:[/red]")
            console.print(result.stderr)
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@migrate.command()
def down():
    """Rollback last migration"""
    console.print("[bold yellow]Rolling back last migration...[/bold yellow]")
    try:
        result = _run_alembic(["downgrade", "-1"])
        if result.returncode == 0:
            console.print("[green]v[/green] Rollback completed successfully")
            if result.stdout:
                console.print(result.stdout)
        else:
            console.print("[red]Error rolling back:[/red]")
            console.print(result.stderr)
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@migrate.command()
def status():
    """Show migration status"""
    console.print("[bold cyan]Migration status:[/bold cyan]\n")
    try:
        result = _run_alembic(["current"])
        if result.returncode == 0:
            console.print(result.stdout)
        else:
            console.print("[red]Error:[/red]")
            console.print(result.stderr)
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@migrate.command()
@click.argument("message")
def create(message: str):
    """Create a new migration"""
    console.print(f"[bold cyan]Creating migration:[/bold cyan] {message}")
    try:
        result = _run_alembic(["revision", "--autogenerate", "-m", message])
        if result.returncode == 0:
            console.print("[green]v[/green] Migration created successfully")
            if result.stdout:
                console.print(result.stdout)
        else:
            console.print("[red]Error creating migration:[/red]")
            console.print(result.stderr)
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
