"""
Admin dashboard UI routes.
Serves HTML pages for admin interface.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import UserContext, get_optional_user
from app.db.models.user import User
from app.db.session import get_db

# Setup templates
ADMIN_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(ADMIN_DIR / "templates"))


def _get_admin_pages():
    """Return plugin-registered admin pages for sidebar rendering."""
    from app.core.plugin_registry import get_registry
    return get_registry().get_admin_pages()


# Make admin_pages callable in all templates: {{ get_admin_pages() }}
templates.env.globals["get_admin_pages"] = _get_admin_pages

router = APIRouter()


def require_admin_ui(user_context: Optional[UserContext] = Depends(get_optional_user)):
    """Check if user is admin, redirect to login if not."""
    if not user_context or user_context.role != "admin":
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return user_context


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard home page."""
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user, "active": "dashboard"},
    )


@router.get("/api", response_class=HTMLResponse)
async def api_documentation(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Comprehensive API documentation page."""
    return templates.TemplateResponse(
        request,
        "api_docs.html",
        {"user": user, "active": "api"},
    )


@router.get("/auth-docs", response_class=HTMLResponse)
async def auth_docs(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Authentication documentation page."""
    return templates.TemplateResponse(
        request,
        "auth_docs.html",
        {"user": user, "active": "auth-docs"},
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """User management page."""
    return templates.TemplateResponse(
        request,
        "users.html",
        {"user": user, "active": "users"},
    )


@router.get("/users/api", response_class=HTMLResponse)
async def users_api_reference(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """View users & authentication API reference."""
    return templates.TemplateResponse(
        request,
        "users_api.html",
        {"user": user, "active": "users"},
    )


@router.get("/collections", response_class=HTMLResponse)
async def admin_collections(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Collection management page."""
    return templates.TemplateResponse(
        request,
        "collections.html",
        {"user": user, "active": "collections"},
    )


@router.get("/collections/new", response_class=HTMLResponse)
async def create_collection_form(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Create new collection form."""
    return templates.TemplateResponse(
        request,
        "collection_form.html",
        {"user": user, "active": "collections", "collection": None},
    )


@router.get("/collections/{collection_id}/edit", response_class=HTMLResponse)
async def edit_collection_form(
    request: Request,
    collection_id: str,
    user: UserContext = Depends(require_admin_ui),
):
    """Edit collection form."""
    return templates.TemplateResponse(
        request,
        "collection_form.html",
        {"user": user, "active": "collections", "collection_id": collection_id},
    )


@router.get("/collections/{collection_name}/api", response_class=HTMLResponse)
async def collection_api_reference(
    request: Request,
    collection_name: str,
    user: UserContext = Depends(require_admin_ui),
):
    """View collection API reference with code examples."""
    return templates.TemplateResponse(
        request,
        "collection_detail.html",
        {"user": user, "active": "collections", "collection_name": collection_name},
    )


@router.get("/collections/{collection_name}/records", response_class=HTMLResponse)
async def collection_records(
    request: Request,
    collection_name: str,
    user: UserContext = Depends(require_admin_ui),
):
    """View records in a collection."""
    return templates.TemplateResponse(
        request,
        "records.html",
        {"user": user, "active": "collections", "collection_name": collection_name},
    )


@router.get("/collections/{collection_name}/records/new", response_class=HTMLResponse)
async def create_record_form(
    request: Request,
    collection_name: str,
    user: UserContext = Depends(require_admin_ui),
):
    """Create new record form."""
    return templates.TemplateResponse(
        request,
        "record_form.html",
        {"user": user, "active": "collections", "collection_name": collection_name, "record": None},
    )


@router.get("/collections/{collection_name}/records/{record_id}", response_class=HTMLResponse)
async def view_record(
    request: Request,
    collection_name: str,
    record_id: str,
    user: UserContext = Depends(require_admin_ui),
):
    """View record details."""
    return templates.TemplateResponse(
        request,
        "record_detail.html",
        {"user": user, "active": "collections", "collection_name": collection_name, "record_id": record_id},
    )


@router.get("/collections/{collection_name}/records/{record_id}/edit", response_class=HTMLResponse)
async def edit_record_form(
    request: Request,
    collection_name: str,
    record_id: str,
    user: UserContext = Depends(require_admin_ui),
):
    """Edit record form."""
    return templates.TemplateResponse(
        request,
        "record_form.html",
        {"user": user, "active": "collections", "collection_name": collection_name, "record_id": record_id},
    )


@router.get("/files", response_class=HTMLResponse)
async def file_manager(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """File management page."""
    return templates.TemplateResponse(
        request,
        "files.html",
        {"user": user, "active": "files"},
    )


@router.get("/webhooks", response_class=HTMLResponse)
async def admin_webhooks(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Webhook management page."""
    return templates.TemplateResponse(
        request,
        "webhooks.html",
        {"user": user, "active": "webhooks"},
    )


@router.get("/plugins", response_class=HTMLResponse)
async def admin_plugins(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Plugins management page — lists all loaded plugin packages."""
    from app.core.plugin_registry import get_registry
    registry = get_registry()
    # Map plugin_id → admin URL so the template can show an "Open"
    # button only for plugins that register their own admin page.
    admin_pages = {p.plugin_id: p.url for p in registry.get_admin_pages()}
    return templates.TemplateResponse(
        request,
        "plugins.html",
        {
            "user": user,
            "active": "plugins",
            "plugins": registry.get_plugins(),
            "admin_pages": admin_pages,
        },
    )


@router.get("/hooks", response_class=HTMLResponse)
async def admin_hooks(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Hooks management page — lists all loaded Python hook files."""
    from app.core.hook_loader import get_loaded_hooks
    return templates.TemplateResponse(
        request,
        "hooks.html",
        {"user": user, "active": "hooks", "hooks": get_loaded_hooks()},
    )


@router.get("/backups", response_class=HTMLResponse)
async def admin_backups(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Backup management page."""
    return templates.TemplateResponse(
        request,
        "backups.html",
        {"user": user, "active": "backups"},
    )


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """System settings page."""
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"user": user, "active": "settings"},
    )


@router.get("/sessions", response_class=HTMLResponse)
async def admin_sessions(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Session management page — list and revoke active sessions."""
    return templates.TemplateResponse(
        request,
        "sessions.html",
        {"user": user, "active": "sessions"},
    )


@router.get("/ip-rules", response_class=HTMLResponse)
async def admin_ip_rules(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """IP allowlist/blocklist management page."""
    from app.core.config import settings as app_settings
    return templates.TemplateResponse(
        request,
        "ip_rules.html",
        {"user": user,
            "active": "ip_rules",
            "ip_filter_enabled": app_settings.IP_FILTER_ENABLED,},
    )


@router.get("/metrics", response_class=HTMLResponse)
async def admin_metrics(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Metrics dashboard page."""
    return templates.TemplateResponse(
        request,
        "metrics.html",
        {"user": user, "active": "metrics"},
    )


@router.get("/settings/email", response_class=HTMLResponse)
async def admin_email_settings(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Email settings and SMTP configuration page."""
    from app.core.config import settings as app_settings
    return templates.TemplateResponse(
        request,
        "email_settings.html",
        {"user": user,
            "active": "email_settings",
            "smtp_enabled": app_settings.SMTP_ENABLED,
            "smtp_host": app_settings.SMTP_HOST,
            "smtp_port": app_settings.SMTP_PORT,
            "smtp_user": app_settings.SMTP_USER,
            "smtp_from_email": app_settings.SMTP_FROM_EMAIL,
            "smtp_from_name": app_settings.SMTP_FROM_NAME,
            "security_notifications_enabled": app_settings.SECURITY_NOTIFICATIONS_ENABLED,
            "security_login_notifications": app_settings.SECURITY_LOGIN_NOTIFICATIONS,},
    )


@router.get("/profile", response_class=HTMLResponse)
async def admin_profile(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """User profile page."""
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"user": user, "active": "profile"},
    )


@router.get("/realtime", response_class=HTMLResponse)
async def admin_realtime(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Real-time features demo page."""
    return templates.TemplateResponse(
        request,
        "realtime.html",
        {"user": user, "active": "realtime"},
    )


@router.get("/cron", response_class=HTMLResponse)
async def admin_cron(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Cron job management page."""
    return templates.TemplateResponse(
        request,
        "cron.html",
        {"user": user, "active": "cron"},
    )


@router.get("/login", response_class=HTMLResponse)
async def admin_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin login page."""
    # Check if setup is needed
    result = await db.execute(select(User).limit(1))
    if not result.scalar_one_or_none():
        return RedirectResponse(url="/setup", status_code=302)

    return templates.TemplateResponse(request, "login.html")


@router.get("/ai", response_class=HTMLResponse)
async def admin_ai_playground(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """AI Playground — only available when AI Core plugin is loaded."""
    from app.core.plugin_registry import get_registry
    ids = {p.id for p in get_registry().get_plugins()}
    if "ai-core" not in ids:
        raise HTTPException(status_code=404, detail="AI Core plugin not installed")
    return templates.TemplateResponse(
        request,
        "ai_playground.html",
        {"user": user, "active": "ai"},
    )


@router.get("/setup", response_class=HTMLResponse)
async def admin_setup(request: Request, db: AsyncSession = Depends(get_db)):
    """Initial setup page for creating first admin user."""
    # Check if setup is already done
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        return RedirectResponse(url="/admin/login", status_code=302)

    return templates.TemplateResponse(request, "setup.html")
