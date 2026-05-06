#!/usr/bin/env python3
"""
FastCMS Command Line Interface — unified entry point.

This module is the pip-installable CLI entry point. It works both
when installed via `pip install fastcms` and when running from the
source repository.

IMPORTANT: Do NOT import from `app.*` at module level. Commands like
`fastcms init` must work before any .env or database exists. All app
imports are deferred to inside each command function.
"""

import asyncio
import sys
from pathlib import Path

import click

# When running from source (not pip-installed), add the repo root to sys.path
# so that `from app.xxx import ...` works without pip install.
_source_root = Path(__file__).parent.parent
if (_source_root / "app" / "main.py").exists() and str(_source_root) not in sys.path:
    sys.path.insert(0, str(_source_root))


@click.group()
@click.version_option(version="0.1.0", prog_name="FastCMS CLI")
def cli():
    """
    FastCMS Command Line Interface

    Manage users, collections, and settings from the terminal.
    """
    pass


@cli.command()
@click.option("--email", prompt=True, help="Admin email address")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Admin password")
@click.option("--name", prompt=True, help="Admin name")
def create_admin(email: str, password: str, name: str):
    """Create a new admin user."""
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.models.user import User
    from app.db.session import AsyncSessionLocal

    async def _create_admin():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                click.echo(click.style(f"User with email '{email}' already exists!", fg="red"))
                return False

            user = User(
                email=email,
                password_hash=hash_password(password),
                name=name,
                role="admin",
                verified=True,
            )

            db.add(user)
            await db.commit()
            await db.refresh(user)

            click.echo(click.style("Admin user created successfully!", fg="green"))
            click.echo(f"   Email: {user.email}")
            click.echo(f"   Name: {user.name}")
            click.echo(f"   Role: {user.role}")
            click.echo(f"   ID: {user.id}")
            return True

    try:
        success = asyncio.run(_create_admin())
        sys.exit(0 if success else 1)
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red"))
        sys.exit(1)


@cli.command()
@click.option("--email", prompt=True, help="User email address")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="User password")
@click.option("--name", prompt=True, help="User name")
@click.option("--role", type=click.Choice(["admin", "user"]), default="user", help="User role")
def create_user(email: str, password: str, name: str, role: str):
    """Create a new user."""
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.models.user import User
    from app.db.session import AsyncSessionLocal

    async def _create_user():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                click.echo(click.style(f"User with email '{email}' already exists!", fg="red"))
                return False

            user = User(
                email=email,
                password_hash=hash_password(password),
                name=name,
                role=role,
                verified=role == "admin",
            )

            db.add(user)
            await db.commit()
            await db.refresh(user)

            click.echo(click.style(f"{'Admin' if role == 'admin' else 'User'} created successfully!", fg="green"))
            click.echo(f"   Email: {user.email}")
            click.echo(f"   Name: {user.name}")
            click.echo(f"   Role: {user.role}")
            click.echo(f"   Verified: {user.verified}")
            click.echo(f"   ID: {user.id}")
            return True

    try:
        success = asyncio.run(_create_user())
        sys.exit(0 if success else 1)
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red"))
        sys.exit(1)


@cli.command()
def list_users():
    """List all users."""
    from sqlalchemy import select

    from app.db.models.user import User
    from app.db.session import AsyncSessionLocal

    async def _list_users():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).order_by(User.created.desc()))
            users = result.scalars().all()

            if not users:
                click.echo(click.style("No users found.", fg="yellow"))
                return

            click.echo(click.style(f"\nFound {len(users)} user(s):\n", fg="cyan", bold=True))

            for user in users:
                role_color = "green" if user.role == "admin" else "blue"
                verified_icon = "v" if user.verified else "x"

                click.echo(f"  {click.style('*', fg=role_color)} {click.style(user.email, bold=True)}")
                click.echo(f"    Name: {user.name or 'N/A'}")
                click.echo(f"    Role: {click.style(user.role.upper(), fg=role_color)}")
                click.echo(f"    Verified: {verified_icon}")
                click.echo(f"    ID: {user.id}")
                click.echo(f"    Created: {user.created.strftime('%Y-%m-%d %H:%M:%S')}")
                click.echo()

    try:
        asyncio.run(_list_users())
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red"))
        sys.exit(1)


@cli.command()
@click.option("--name", prompt=True, help="Collection name (lowercase, letters, numbers, underscores)")
@click.option("--type", "collection_type",
              type=click.Choice(["base", "auth", "view"]),
              default="base",
              help="Collection type")
@click.option("--field", "fields", multiple=True,
              help="Field definition (name:type, e.g., 'title:text' or 'price:number')")
def create_collection(name: str, collection_type: str, fields: tuple):
    """
    Create a new collection.

    Example:
        fastcms create-collection --name products --type base --field title:text --field price:number --field active:bool
    """
    from sqlalchemy import select

    from app.db.models.collection import Collection
    from app.db.session import AsyncSessionLocal

    async def _create_collection():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Collection).where(Collection.name == name))
            existing = result.scalar_one_or_none()

            if existing:
                click.echo(click.style(f"Collection '{name}' already exists!", fg="red"))
                return False

            schema = []
            if fields:
                for field_def in fields:
                    if ":" not in field_def:
                        click.echo(click.style(f"Invalid field format: {field_def}. Use 'name:type'", fg="red"))
                        return False

                    field_name, field_type = field_def.split(":", 1)

                    valid_types = ["text", "number", "bool", "email", "url", "date", "select", "relation", "file", "json", "editor"]
                    if field_type not in valid_types:
                        click.echo(click.style(f"Invalid field type: {field_type}. Must be one of: {', '.join(valid_types)}", fg="red"))
                        return False

                    schema.append({
                        "name": field_name,
                        "type": field_type,
                        "validation": {}
                    })

            if collection_type == "auth":
                click.echo(click.style("Auth collection will automatically include: email, password, verified, role, token_key", fg="cyan"))

            collection = Collection(
                name=name,
                type=collection_type,
                schema={"fields": schema} if schema else {"fields": []},
                list_rule=None,
                view_rule=None,
                create_rule=None,
                update_rule=None,
                delete_rule=None
            )

            db.add(collection)
            await db.commit()
            await db.refresh(collection)

            click.echo(click.style(f"Collection '{name}' created successfully!", fg="green"))
            click.echo(f"   Type: {collection_type}")
            click.echo(f"   ID: {collection.id}")
            if schema:
                click.echo(f"   Fields: {len(schema)} custom field(s)")
                for field in schema:
                    click.echo(f"     - {field['name']} ({field['type']})")

            click.echo(click.style(f"\n   Tip: Access your collection at /admin/collections/{name}/records", fg="cyan"))
            return True

    try:
        success = asyncio.run(_create_collection())
        sys.exit(0 if success else 1)
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red"))
        sys.exit(1)


@cli.command()
def list_collections():
    """List all collections."""
    from sqlalchemy import select

    from app.db.models.collection import Collection
    from app.db.session import AsyncSessionLocal

    async def _list_collections():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Collection).order_by(Collection.created.desc()))
            collections = result.scalars().all()

            if not collections:
                click.echo(click.style("No collections found.", fg="yellow"))
                return

            click.echo(click.style(f"\nFound {len(collections)} collection(s):\n", fg="cyan", bold=True))

            for collection in collections:
                type_color = {
                    "base": "blue",
                    "auth": "green",
                    "view": "magenta"
                }.get(collection.type, "white")

                click.echo(f"  {click.style('*', fg=type_color)} {click.style(collection.name, bold=True)}")
                click.echo(f"    Type: {click.style(collection.type.upper(), fg=type_color)}")
                click.echo(f"    ID: {collection.id}")

                fields = collection.schema.get("fields", []) if collection.schema else []
                click.echo(f"    Fields: {len(fields)}")
                if fields:
                    field_names = [f['name'] for f in fields[:3]]
                    more = f" (+{len(fields) - 3} more)" if len(fields) > 3 else ""
                    click.echo(f"      {', '.join(field_names)}{more}")

                click.echo(f"    Created: {collection.created.strftime('%Y-%m-%d %H:%M:%S')}")
                click.echo()

    try:
        asyncio.run(_list_collections())
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red"))
        sys.exit(1)


@cli.command()
@click.argument("collection_name")
def delete_collection(collection_name: str):
    """Delete a collection by name."""
    from sqlalchemy import select

    from app.db.models.collection import Collection
    from app.db.session import AsyncSessionLocal

    if not click.confirm(click.style(f"Are you sure you want to delete collection '{collection_name}'? This cannot be undone!", fg="yellow")):
        click.echo("Deletion cancelled.")
        return

    async def _delete_collection():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Collection).where(Collection.name == collection_name))
            collection = result.scalar_one_or_none()

            if not collection:
                click.echo(click.style(f"Collection '{collection_name}' not found!", fg="red"))
                return False

            await db.delete(collection)
            await db.commit()

            click.echo(click.style(f"Collection '{collection_name}' deleted successfully!", fg="green"))
            return True

    try:
        success = asyncio.run(_delete_collection())
        sys.exit(0 if success else 1)
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red"))
        sys.exit(1)


@cli.command()
def info():
    """Display FastCMS system information."""
    from sqlalchemy import select

    from app.db.models.collection import Collection
    from app.db.models.user import User
    from app.db.session import AsyncSessionLocal

    click.echo(click.style("\nFastCMS System Information\n", fg="cyan", bold=True))

    async def _check_db():
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User))
                users = result.scalars().all()

                result = await db.execute(select(Collection))
                collections = result.scalars().all()

                return len(users), len(collections)
        except Exception:
            return None, None

    users_count, collections_count = asyncio.run(_check_db())

    if users_count is not None:
        click.echo(f"  {click.style('OK', fg='green')} Database: Connected")
        click.echo(f"  {click.style('*', fg='blue')} Users: {users_count}")
        click.echo(f"  {click.style('*', fg='blue')} Collections: {collections_count}")
    else:
        click.echo(f"  {click.style('FAIL', fg='red')} Database: Connection failed")

    data_dir = Path("data")
    if data_dir.exists():
        db_file = data_dir / "app.db"
        backups_dir = data_dir / "backups"

        click.echo(f"\n  {click.style('*', fg='blue')} Data directory: {data_dir.absolute()}")
        if db_file.exists():
            size_mb = db_file.stat().st_size / (1024 * 1024)
            click.echo(f"  {click.style('*', fg='blue')} Database size: {size_mb:.2f} MB")

        if backups_dir.exists():
            backups = list(backups_dir.glob("*.zip"))
            click.echo(f"  {click.style('*', fg='blue')} Backups: {len(backups)}")

    click.echo(f"\n  Run 'fastcms --help' to see all available commands\n")


# Import additional commands from cli/ module
try:
    from cli.commands.dev import dev
    from cli.commands.init import init
    from cli.commands.migrate import migrate
    from cli.commands.plugin import plugin
    from cli.commands.seed import seed

    cli.add_command(dev)
    cli.add_command(init)
    cli.add_command(migrate)
    cli.add_command(plugin)
    cli.add_command(seed)
except ImportError:
    pass  # cli module not available (e.g., standalone script usage)


if __name__ == "__main__":
    cli()
