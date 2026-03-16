"""
Project initialization command — scaffolds a complete FastCMS project.
"""
import os
import secrets
import shutil

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.command()
@click.argument("project_name")
@click.option(
    "--database",
    type=click.Choice(["sqlite", "postgres"]),
    default="sqlite",
    help="Database type",
)
@click.option("--template", type=str, help="Project template (blog, ecommerce, saas)")
def init(project_name: str, database: str, template: str):
    """
    Initialize a new FastCMS project

    Example: fastcms init my-project --database sqlite
    """
    console.print(f"\n[bold cyan]Creating FastCMS project:[/bold cyan] {project_name}\n")

    # Create project directory
    if os.path.exists(project_name):
        console.print(f"[red]Error:[/red] Directory '{project_name}' already exists")
        return

    # Generate a secure SECRET_KEY
    secret_key = secrets.token_hex(32)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating project structure...", total=None)

        # Create directories
        os.makedirs(project_name)
        os.makedirs(f"{project_name}/data")
        os.makedirs(f"{project_name}/data/files")
        os.makedirs(f"{project_name}/plugins", exist_ok=True)
        os.makedirs(f"{project_name}/hooks", exist_ok=True)

        progress.update(task, description="Copying migrations...")

        # Copy migrations and alembic.ini from bundled resources
        try:
            from app._bundled import get_alembic_ini, get_migrations_dir

            migrations_src = get_migrations_dir()
            shutil.copytree(str(migrations_src), f"{project_name}/migrations")

            alembic_ini_src = get_alembic_ini()
            shutil.copy2(str(alembic_ini_src), f"{project_name}/alembic.ini")
        except (ImportError, FileNotFoundError) as e:
            console.print(f"\n[yellow]Warning:[/yellow] Could not copy migrations: {e}")
            console.print("[dim]You can copy migrations manually from the FastCMS repository.[/dim]")

        progress.update(task, description="Creating configuration files...")

        # Database URL based on choice
        if database == "sqlite":
            db_url = "sqlite+aiosqlite:///./data/app.db"
        else:
            db_url = "postgresql+asyncpg://user:password@localhost:5432/fastcms"

        # Create .env file
        env_content = f"""# FastCMS Configuration

# Application
APP_NAME=FastCMS
APP_VERSION=0.1.0
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true
ENVIRONMENT=development
BASE_URL=http://localhost:8000

# Database
DATABASE_URL={db_url}

# Security
SECRET_KEY={secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
CORS_ALLOW_CREDENTIALS=true

# File Storage
STORAGE_TYPE=local
MAX_FILE_SIZE=10485760
LOCAL_STORAGE_PATH=./data/files

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@fastcms.dev
SMTP_FROM_NAME=FastCMS

# OAuth Providers (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
"""
        with open(f"{project_name}/.env", "w", encoding="utf-8") as f:
            f.write(env_content)

        # Create README
        readme_content = f"""# {project_name}

FastCMS project created with the FastCMS CLI.

## Getting Started

1. Navigate to your project:
   ```bash
   cd {project_name}
   ```

2. Update the `.env` file with your configuration

3. Run database migrations:
   ```bash
   fastcms migrate up
   ```

4. Create an admin user:
   ```bash
   fastcms create-admin
   ```

5. Start the development server:
   ```bash
   fastcms dev
   ```

## Access

- Admin Dashboard: http://localhost:8000/admin
- API Documentation: http://localhost:8000/docs (debug mode only)
- Health Check: http://localhost:8000/health

## Project Structure

```
{project_name}/
  .env              # Configuration
  alembic.ini       # Database migration config
  data/             # Database and uploaded files
  migrations/       # Database migration scripts
  plugins/          # Custom plugins (drop-in)
  hooks/            # Custom hooks (drop-in)
```

## Documentation

- Full Documentation: https://docs.fastcms.dev
- GitHub: https://github.com/fastcms/fastcms
"""
        with open(f"{project_name}/README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)

        # Create .gitignore
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.venv

# FastCMS
data/
.env
*.db
*.db-journal
*.db-shm
*.db-wal

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
"""
        with open(f"{project_name}/.gitignore", "w", encoding="utf-8") as f:
            f.write(gitignore_content)

        progress.update(task, description="Project created successfully!")

    console.print(f"\n[bold green]Success![/bold green] Project '{project_name}' created.\n")

    console.print("[bold]Quick Start:[/bold]\n")
    console.print(f"  1. [bold cyan]cd {project_name}[/bold cyan]")
    console.print(f"  2. [bold cyan]fastcms migrate up[/bold cyan]       [dim]# Create database tables[/dim]")
    console.print(f"  3. [bold cyan]fastcms create-admin[/bold cyan]     [dim]# Create admin user[/dim]")
    console.print(f"  4. [bold cyan]fastcms dev[/bold cyan]              [dim]# Start development server[/dim]\n")

    console.print("[bold]Access:[/bold]")
    console.print(f"  Admin Dashboard: [link]http://localhost:8000/admin[/link]")
    console.print(f"  API Docs:        [link]http://localhost:8000/docs[/link]")
    console.print(f"  Health Check:    [link]http://localhost:8000/health[/link]\n")
