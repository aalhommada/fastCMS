"""
Plugin management commands — install from registry, create scaffolds, list installed.
"""

import io
import os
import shutil
import tarfile
import textwrap

import click
from rich.console import Console
from rich.table import Table

console = Console()

# Official plugin registry — maps short names to directory names in the
# fastcms-plugins GitHub repo.
PLUGIN_REGISTRY = {
    "ai-core": {
        "dir": "ai_core",
        "description": "LLM provider abstraction (OpenAI, Anthropic, Ollama)",
        "depends": [],
    },
    "ai-vectors": {
        "dir": "ai_vectors",
        "description": "Embedding storage and semantic search",
        "depends": ["ai-core"],
    },
    "ai-rag": {
        "dir": "ai_rag",
        "description": "Retrieval-Augmented Generation pipeline",
        "depends": ["ai-core", "ai-vectors"],
    },
    "ai-agents": {
        "dir": "ai_agents",
        "description": "Autonomous agents with FastCMS data tools",
        "depends": ["ai-core"],
    },
    "example": {
        "dir": "example_plugin",
        "description": "Reference plugin demonstrating all capabilities",
        "depends": [],
    },
}

GITHUB_REPO = "aalhommada/fastcms-plugins"
GITHUB_TARBALL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.tar.gz"


@click.group()
def plugin():
    """Plugin management commands"""
    pass


@plugin.command("install")
@click.argument("name")
@click.option("--force", is_flag=True, help="Overwrite existing plugin")
def install_plugin(name: str, force: bool):
    """
    Install a plugin from the official registry.

    Available plugins: ai-core, ai-vectors, ai-rag, ai-agents, example
    """
    import httpx

    if name not in PLUGIN_REGISTRY:
        console.print(f"[red]Error:[/red] Unknown plugin '{name}'")
        console.print(f"\n[bold]Available plugins:[/bold]")
        for pid, info in PLUGIN_REGISTRY.items():
            console.print(f"  [cyan]{pid}[/cyan] — {info['description']}")
        return

    entry = PLUGIN_REGISTRY[name]
    dest = os.path.join("plugins", entry["dir"])

    if os.path.exists(dest) and not force:
        console.print(f"[yellow]Plugin '{name}' already exists at {dest}[/yellow]")
        console.print("[dim]Use --force to overwrite[/dim]")
        return

    # Check dependencies
    missing = []
    for dep in entry["depends"]:
        dep_dir = os.path.join("plugins", PLUGIN_REGISTRY[dep]["dir"])
        if not os.path.exists(dep_dir):
            missing.append(dep)

    if missing:
        console.print(f"[yellow]Note:[/yellow] '{name}' depends on: {', '.join(missing)}")
        if not click.confirm("Install dependencies too?", default=True):
            console.print("[dim]Skipping dependency installation[/dim]")
        else:
            for dep in missing:
                _download_plugin(dep, force=force)

    _download_plugin(name, force=force)


def _download_plugin(name: str, force: bool = False):
    """Download and extract a single plugin from the GitHub repo."""
    import httpx

    entry = PLUGIN_REGISTRY[name]
    dest = os.path.join("plugins", entry["dir"])

    if os.path.exists(dest) and not force:
        console.print(f"  [dim]'{name}' already installed, skipping[/dim]")
        return

    console.print(f"[cyan]Downloading plugin '{name}'...[/cyan]")

    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            resp = client.get(GITHUB_TARBALL)
            resp.raise_for_status()

        # Extract the specific plugin directory from the tarball
        tar_bytes = io.BytesIO(resp.content)
        with tarfile.open(fileobj=tar_bytes, mode="r:gz") as tar:
            # Tarball root is "fastcms-plugins-main/"
            prefix = None
            for member in tar.getmembers():
                parts = member.name.split("/")
                if prefix is None:
                    prefix = parts[0]
                # Match: <root>/<plugin_dir>/...
                if len(parts) >= 2 and parts[1] == entry["dir"]:
                    # Strip the root prefix so we get just the plugin dir
                    member.name = "/".join(parts[1:])
                    tar.extract(member, path="plugins")

        if os.path.exists(dest):
            console.print(f"  [green]v[/green] Installed '{name}' -> {dest}")
        else:
            console.print(f"  [red]Error:[/red] Plugin directory not found in repository")

    except httpx.HTTPError as e:
        console.print(f"[red]Error downloading:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


@plugin.command("create")
@click.argument("name")
def create_plugin(name: str):
    """
    Scaffold a new plugin.

    Creates a plugin directory with boilerplate code.

    Example: fastcms plugin create my-analytics
    """
    # Normalize name to valid Python package name
    dir_name = name.replace("-", "_").replace(" ", "_").lower()
    dest = os.path.join("plugins", dir_name)

    if os.path.exists(dest):
        console.print(f"[red]Error:[/red] Directory '{dest}' already exists")
        return

    console.print(f"[cyan]Creating plugin '{name}'...[/cyan]")

    os.makedirs(dest, exist_ok=True)

    # __init__.py
    init_content = textwrap.dedent(f'''\
        """
        {name} plugin for FastCMS
        """

        PLUGIN_META = {{
            "id": "{name}",
            "name": "{name.replace("-", " ").replace("_", " ").title()}",
            "version": "0.1.0",
            "author": "",
            "description": "A custom FastCMS plugin",
        }}


        def register(ctx) -> None:
            """Register plugin routes, hooks, and admin pages."""
            from .routes import router

            ctx.include_router(router, prefix="/{dir_name}", tags=["{name.replace("-", " ").replace("_", " ").title()}"])

            ctx.add_admin_page(
                nav_id="{name}",
                label="{name.replace("-", " ").replace("_", " ").title()}",
                icon="fa-plug",
                url="/admin/plugins/{name}",
            )
    ''')

    with open(os.path.join(dest, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(init_content)

    # routes.py
    routes_content = textwrap.dedent(f'''\
        """
        {name} plugin routes
        """

        from fastapi import APIRouter, Depends

        router = APIRouter()


        @router.get("/status")
        async def status():
            """Plugin health check"""
            return {{"status": "ok", "plugin": "{name}"}}
    ''')

    with open(os.path.join(dest, "routes.py"), "w", encoding="utf-8") as f:
        f.write(routes_content)

    # requirements.txt (empty)
    with open(os.path.join(dest, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("# Add plugin-specific dependencies here\n")

    console.print(f"  [green]v[/green] Created {dest}/")
    console.print(f"    [dim]__init__.py[/dim]  — Plugin metadata + register()")
    console.print(f"    [dim]routes.py[/dim]    — API routes (starter endpoint at /status)")
    console.print(f"    [dim]requirements.txt[/dim]")
    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  1. Edit [bold]{dest}/routes.py[/bold] to add your API endpoints")
    console.print(f"  2. Restart FastCMS — your plugin loads automatically")
    console.print(f"  3. Access your plugin at [bold]/api/v1/plugins/{dir_name}/status[/bold]")


@plugin.command("list")
def list_plugins():
    """List installed and available plugins"""
    # Installed plugins
    plugins_dir = "plugins"
    installed = set()
    if os.path.exists(plugins_dir):
        for item in os.listdir(plugins_dir):
            init_file = os.path.join(plugins_dir, item, "__init__.py")
            if os.path.isdir(os.path.join(plugins_dir, item)) and os.path.exists(init_file):
                installed.add(item)

    console.print("[bold cyan]Installed Plugins:[/bold cyan]\n")

    if installed:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Directory")
        table.add_column("Status")

        for name in sorted(installed):
            table.add_row(name, "[green]installed[/green]")

        console.print(table)
    else:
        console.print("  [dim]No plugins installed. Use 'fastcms plugin install <name>' to add one.[/dim]")

    console.print(f"\n[bold cyan]Available from Registry:[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Depends On")
    table.add_column("Status")

    for pid, info in PLUGIN_REGISTRY.items():
        is_installed = info["dir"] in installed
        status = "[green]installed[/green]" if is_installed else "[dim]not installed[/dim]"
        deps = ", ".join(info["depends"]) if info["depends"] else "-"
        table.add_row(pid, info["description"], deps, status)

    console.print(table)
