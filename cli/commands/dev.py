"""
Development server command
"""
import asyncio
import threading
import time
import urllib.request
import webbrowser

import click
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


def _open_browser_when_ready(url: str, health_url: str, timeout: float = 15.0) -> None:
    """Poll the health endpoint, then open the browser. Runs in a thread.

    Why not just sleep(1) and open: cold-boot can take longer than that on
    the first start (DB init + plugin discovery). Polling /health is more
    reliable.
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as resp:
                if 200 <= resp.status < 300:
                    webbrowser.open(url)
                    return
        except Exception:
            pass
        time.sleep(0.3)


async def check_first_run():
    """Check if this is the first run (no admin users exist)"""
    try:
        from app.db.session import get_db_context
        from sqlalchemy import text

        async with get_db_context() as db:
            result = await db.execute(text("SELECT COUNT(*) FROM users WHERE role = 'admin'"))
            admin_count = result.scalar()
            return admin_count == 0
    except Exception:
        # If there's an error (e.g., table doesn't exist), consider it first run
        return True


def prompt_create_admin():
    """Prompt user to create an admin user"""
    console.print()
    console.print(Panel.fit(
        "[bold yellow]⚠ No admin user found![/bold yellow]\n\n"
        "It looks like this is your first time running fastCMS.\n"
        "You'll need an admin user to manage your instance.\n\n"
        "[dim]An admin can:[/dim]\n"
        "  • Create and manage collections\n"
        "  • Manage users and permissions\n"
        "  • Access system settings\n"
        "  • View logs and backups",
        title="[bold cyan]Welcome to fastCMS! 🚀[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    if Confirm.ask("[bold]Would you like to create an admin user now?[/bold]", default=True):
        console.print()
        import subprocess
        import sys
        # Run the interactive user creation
        result = subprocess.run(
            ["fastcms", "create-admin"],
            check=False
        )
        if result.returncode == 0:
            console.print()
            console.print("[bold green]✓ Great! Your admin user is ready.[/bold green]")
            console.print("[dim]Starting the server...[/dim]\n")
            return True
        else:
            console.print()
            console.print("[yellow]Admin creation skipped. You can create one later with:[/yellow]")
            console.print("[bold]  fastcms users create --interactive[/bold]\n")
            return False
    else:
        console.print()
        console.print("[yellow]Skipping admin creation. You can create one later with:[/yellow]")
        console.print("[bold]  fastcms users create admin@example.com --admin[/bold]\n")
        return False


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload/--no-reload", default=True, help="Enable auto-reload")
@click.option("--skip-check", is_flag=True, help="Skip first-run admin check")
@click.option("--open/--no-open", "open_browser", default=True,
              help="Open the admin in a browser when the server is ready (default: on)")
def dev(host: str, port: int, reload: bool, skip_check: bool, open_browser: bool):
    """
    Start the FastCMS development server

    Example: fastcms dev --port 8000 --reload
    """
    console.print(f"\n[bold cyan]🚀 Starting fastCMS Development Server[/bold cyan]\n")

    # Check for first run unless explicitly skipped
    if not skip_check:
        try:
            is_first_run = asyncio.run(check_first_run())
            if is_first_run:
                prompt_create_admin()
        except Exception as e:
            console.print(f"[dim]Note: Could not check for admin users ({str(e)})[/dim]\n")

    console.print(f"[bold]Configuration:[/bold]")
    console.print(f"  • Host: [cyan]{host}[/cyan]")
    console.print(f"  • Port: [cyan]{port}[/cyan]")
    console.print(f"  • Auto-reload: [cyan]{'enabled' if reload else 'disabled'}[/cyan]\n")

    console.print("[bold]Access your fastCMS instance at:[/bold]")
    console.print(f"  • API Documentation: [link]http://localhost:{port}/docs[/link]")
    console.print(f"  • Health Check: [link]http://localhost:{port}/health[/link]")
    console.print(f"  • Admin Dashboard: [link]http://localhost:{port}/admin[/link]\n")

    console.print("[dim]Press CTRL+C to stop the server[/dim]\n")
    console.print("─" * 60 + "\n")

    # When the server is ready, optionally open the admin in a browser.
    # Runs in a background thread so it doesn't block uvicorn's startup.
    # Uses 127.0.0.1 in the visit URL even when binding to 0.0.0.0, since
    # the browser is on the same machine.
    if open_browser:
        visit_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
        threading.Thread(
            target=_open_browser_when_ready,
            args=(
                f"http://{visit_host}:{port}/admin",
                f"http://{visit_host}:{port}/health",
            ),
            daemon=True,
        ).start()

    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )
    except KeyboardInterrupt:
        console.print("\n\n[bold cyan]Server stopped. Thanks for using fastCMS! 👋[/bold cyan]\n")
