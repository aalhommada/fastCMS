"""
Seed command — populate the database with demo data for development.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import click
from rich.console import Console

console = Console()

DEMO_COLLECTIONS = [
    {
        "name": "posts",
        "type": "base",
        "schema": {
            "fields": [
                {"name": "title", "type": "text", "validation": {"required": True}},
                {"name": "content", "type": "editor", "validation": {}},
                {"name": "slug", "type": "text", "validation": {}},
                {"name": "published", "type": "bool", "validation": {}},
                {"name": "publish_date", "type": "date", "validation": {}},
            ]
        },
    },
    {
        "name": "categories",
        "type": "base",
        "schema": {
            "fields": [
                {"name": "name", "type": "text", "validation": {"required": True}},
                {"name": "description", "type": "text", "validation": {}},
                {"name": "color", "type": "text", "validation": {}},
            ]
        },
    },
    {
        "name": "products",
        "type": "base",
        "schema": {
            "fields": [
                {"name": "name", "type": "text", "validation": {"required": True}},
                {"name": "description", "type": "text", "validation": {}},
                {"name": "price", "type": "number", "validation": {}},
                {"name": "sku", "type": "text", "validation": {}},
                {"name": "in_stock", "type": "bool", "validation": {}},
            ]
        },
    },
]

DEMO_RECORDS = {
    "posts": [
        {
            "title": "Getting Started with FastCMS",
            "content": "<p>FastCMS is a powerful Backend-as-a-Service built with Python and FastAPI. In this guide, we'll walk through the basics.</p>",
            "slug": "getting-started",
            "published": True,
            "publish_date": "2026-03-01",
        },
        {
            "title": "Building a Blog with FastCMS",
            "content": "<p>Learn how to create a complete blog using FastCMS collections, records, and the admin dashboard.</p>",
            "slug": "building-a-blog",
            "published": True,
            "publish_date": "2026-03-05",
        },
        {
            "title": "Authentication Deep Dive",
            "content": "<p>Explore JWT tokens, OAuth providers, 2FA, and API keys in FastCMS.</p>",
            "slug": "auth-deep-dive",
            "published": False,
            "publish_date": None,
        },
    ],
    "categories": [
        {"name": "Technology", "description": "Tech news and tutorials", "color": "#3B82F6"},
        {"name": "Design", "description": "UI/UX and visual design", "color": "#8B5CF6"},
        {"name": "Business", "description": "Business and strategy", "color": "#10B981"},
    ],
    "products": [
        {
            "name": "FastCMS Pro License",
            "description": "Commercial license with priority support",
            "price": 99.00,
            "sku": "FCMS-PRO-001",
            "in_stock": True,
        },
        {
            "name": "FastCMS Enterprise",
            "description": "Enterprise license with SLA and dedicated support",
            "price": 499.00,
            "sku": "FCMS-ENT-001",
            "in_stock": True,
        },
        {
            "name": "Plugin Development Kit",
            "description": "Tools and templates for building FastCMS plugins",
            "price": 0.00,
            "sku": "FCMS-PDK-001",
            "in_stock": True,
        },
    ],
}


@click.command()
@click.option("--force", is_flag=True, help="Drop existing demo collections before seeding")
def seed(force: bool):
    """
    Seed the database with demo data.

    Creates sample collections (posts, categories, products) with
    example records for development and testing.
    """
    console.print("\n[bold cyan]Seeding demo data...[/bold cyan]\n")

    async def _seed():
        from sqlalchemy import text

        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            created_collections = 0
            created_records = 0

            for coll_def in DEMO_COLLECTIONS:
                name = coll_def["name"]

                # Check if collection already exists
                result = await db.execute(
                    text("SELECT id FROM collections WHERE name = :name"),
                    {"name": name},
                )
                existing = result.fetchone()

                if existing and not force:
                    console.print(f"  [yellow]skip[/yellow] Collection '{name}' already exists")
                    continue

                if existing and force:
                    # Delete records table and collection metadata
                    try:
                        await db.execute(text(f'DROP TABLE IF EXISTS "record_{name}"'))
                    except Exception:
                        pass
                    await db.execute(
                        text("DELETE FROM collections WHERE name = :name"),
                        {"name": name},
                    )
                    await db.commit()
                    console.print(f"  [yellow]dropped[/yellow] Existing collection '{name}'")

                # Create collection
                import json

                coll_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                await db.execute(
                    text(
                        "INSERT INTO collections "
                        "(id, name, type, schema, options, system, created, updated) "
                        "VALUES (:id, :name, :type, :schema, :options, :system, :created, :updated)"
                    ),
                    {
                        "id": coll_id,
                        "name": name,
                        "type": coll_def["type"],
                        "schema": json.dumps(coll_def["schema"]),
                        "options": json.dumps({}),
                        "system": False,
                        "created": now,
                        "updated": now,
                    },
                )
                await db.commit()

                # Create the records table
                fields = coll_def["schema"]["fields"]
                columns = ['id TEXT PRIMARY KEY', 'created TEXT', 'updated TEXT']
                for field in fields:
                    col_type = _field_to_sql(field["type"])
                    columns.append(f'"{field["name"]}" {col_type}')

                create_sql = f'CREATE TABLE IF NOT EXISTS "record_{name}" ({", ".join(columns)})'
                await db.execute(text(create_sql))
                await db.commit()

                created_collections += 1
                console.print(f"  [green]v[/green] Created collection '{name}' ({len(fields)} fields)")

                # Insert demo records
                records = DEMO_RECORDS.get(name, [])
                for record_data in records:
                    record_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc).isoformat()

                    col_names = ["id", "created", "updated"] + list(record_data.keys())
                    placeholders = [f":{c}" for c in col_names]
                    values = {
                        "id": record_id,
                        "created": now,
                        "updated": now,
                        **record_data,
                    }

                    quoted_cols = ", ".join(f'"{c}"' for c in col_names)
                    insert_sql = (
                        f'INSERT INTO "record_{name}" '
                        f"({quoted_cols}) "
                        f'VALUES ({", ".join(placeholders)})'
                    )
                    await db.execute(text(insert_sql), values)
                    created_records += 1

                await db.commit()
                console.print(f"    [dim]+ {len(records)} records[/dim]")

            console.print(
                f"\n[bold green]Done![/bold green] "
                f"Created {created_collections} collections, {created_records} records.\n"
            )

            if created_collections == 0:
                console.print("[dim]All collections already existed. Use --force to recreate them.[/dim]\n")

    try:
        asyncio.run(_seed())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def _field_to_sql(field_type: str) -> str:
    """Map FastCMS field type to SQLite column type."""
    mapping = {
        "text": "TEXT",
        "editor": "TEXT",
        "number": "REAL",
        "bool": "INTEGER",
        "email": "TEXT",
        "url": "TEXT",
        "date": "TEXT",
        "select": "TEXT",
        "relation": "TEXT",
        "file": "TEXT",
        "json": "TEXT",
        "autodate": "TEXT",
    }
    return mapping.get(field_type, "TEXT")
