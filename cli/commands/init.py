"""
Project initialization command
"""
import os
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

        progress.update(task, description="Creating configuration files...")

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
DATABASE_URL={'sqlite+aiosqlite:///./data/app.db' if database == 'sqlite' else 'postgresql+asyncpg://user:password@localhost:5432/fastcms'}

# Security
SECRET_KEY=your-secret-key-here-change-this-in-production
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

1. Install dependencies:
   ```bash
   cd {project_name}
   pip install fastcms[ai,dev]
   ```

2. Update the `.env` file with your configuration

3. Run database migrations:
   ```bash
   fastcms migrate up
   ```

4. Start the development server:
   ```bash
   fastcms dev
   ```

5. Visit http://localhost:8000/docs for API documentation

## Admin Access

Create an admin user:
```bash
fastcms users create admin@example.com --admin --password yourpassword
```

Then visit http://localhost:8000/admin to access the admin dashboard.

## Documentation

- API Docs: http://localhost:8000/docs
- Admin Dashboard: http://localhost:8000/admin
- Full Documentation: https://docs.fastcms.dev

## Features

- 🚀 Dynamic Collections & Records
- 🔐 Authentication & Authorization
- 📁 File Storage (Local/S3)
- ⚡ Real-time Subscriptions
- 🔍 Full-Text Search
- 🪝 Webhooks
- 🤖 AI-powered features
- 📊 Admin Dashboard

## Support

- GitHub: https://github.com/fastcms/fastcms
- Issues: https://github.com/fastcms/fastcms/issues
- Docs: https://docs.fastcms.dev
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

    console.print(f"\n[bold green]✓ Success![/bold green] Project '{project_name}' created successfully!\n")

    console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]          🎉 Project Ready!               [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]\n")

    console.print("[bold]Quick Start Guide:[/bold]\n")
    console.print(f"  1️⃣  Navigate to your project:")
    console.print(f"      [bold cyan]cd {project_name}[/bold cyan]\n")

    console.print(f"  2️⃣  Review and update your configuration:")
    console.print(f"      [bold cyan]nano .env[/bold cyan]  [dim](or use your favorite editor)[/dim]\n")

    console.print(f"  3️⃣  Run database migrations:")
    console.print(f"      [bold cyan]fastcms migrate up[/bold cyan]\n")

    console.print(f"  4️⃣  Start the development server:")
    console.print(f"      [bold cyan]fastcms dev[/bold cyan]\n")

    console.print("[dim]The server will prompt you to create an admin user on first run![/dim]\n")

    console.print("[bold]Or create an admin user now:[/bold]")
    console.print(f"      [bold cyan]cd {project_name} && fastcms users create --interactive[/bold cyan]\n")

    console.print("[bold]Useful Links:[/bold]")
    console.print(f"  • API Docs: [link]http://localhost:8000/docs[/link]")
    console.print(f"  • Admin Dashboard: [link]http://localhost:8000/admin[/link]")
    console.print(f"  • Health Check: [link]http://localhost:8000/health[/link]\n")

    console.print("[dim]Need help? Check out USER_GUIDE.md in your project![/dim]\n")
