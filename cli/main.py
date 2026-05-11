"""
FastCMS CLI - Main entry point
"""
import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group()
@click.version_option(version="0.1.5", prog_name="FastCMS")
def cli():
    """
    FastCMS - AI-Native Backend-as-a-Service CLI

    Manage your FastCMS projects, collections, and users.
    """
    pass


@cli.command()
def info():
    """Show FastCMS information"""
    console.print(
        Panel.fit(
            "[bold cyan]FastCMS - AI-Native Backend-as-a-Service[/bold cyan]\n"
            "[dim]Version: 0.1.5[/dim]\n"
            "[dim]Python-based Backend-as-a-Service with AI capabilities[/dim]\n\n"
            "[yellow]Features:[/yellow]\n"
            "  • Dynamic Collections & Records\n"
            "  • Authentication & Authorization\n"
            "  • File Storage (Local/S3)\n"
            "  • Real-time Subscriptions\n"
            "  • Full-Text Search\n"
            "  • Webhooks\n"
            "  • AI-powered features\n"
            "  • Admin Dashboard\n\n"
            "[green]Get started: fastcms init my-project[/green]",
            title="FastCMS CLI",
            border_style="cyan",
        )
    )


# Import command groups
from cli.commands import dev, init, migrate, collections, users, plugin, seed

cli.add_command(init.init)
cli.add_command(dev.dev)
cli.add_command(migrate.migrate)
cli.add_command(collections.collections)
cli.add_command(users.users)
cli.add_command(plugin.plugin)
cli.add_command(seed.seed)


if __name__ == "__main__":
    cli()
