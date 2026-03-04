"""
Admin dashboard UI routes.
Serves HTML pages for admin interface.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
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

router = APIRouter()


def require_admin_ui(user_context: Optional[UserContext] = Depends(get_optional_user)):
    """Check if user is admin, redirect to login if not."""
    if not user_context or user_context.role != "admin":
        return RedirectResponse(url="/admin/login", status_code=302)
    return user_context


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard home page."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "active": "dashboard"},
    )


@router.get("/api", response_class=HTMLResponse)
async def api_documentation(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Comprehensive API documentation page."""
    return templates.TemplateResponse(
        "api_docs.html",
        {"request": request, "user": user, "active": "api"},
    )


@router.get("/auth-docs", response_class=HTMLResponse)
async def auth_docs(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Authentication documentation page."""
    return templates.TemplateResponse(
        "auth_docs.html",
        {"request": request, "user": user, "active": "auth-docs"},
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """User management page."""
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "user": user, "active": "users"},
    )


@router.get("/users/api", response_class=HTMLResponse)
async def users_api_reference(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """View users & authentication API reference."""
    return templates.TemplateResponse(
        "users_api.html",
        {"request": request, "user": user, "active": "users"},
    )


@router.get("/collections", response_class=HTMLResponse)
async def admin_collections(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Collection management page."""
    return templates.TemplateResponse(
        "collections.html",
        {"request": request, "user": user, "active": "collections"},
    )


@router.get("/collections/new", response_class=HTMLResponse)
async def create_collection_form(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Create new collection form."""
    return templates.TemplateResponse(
        "collection_form.html",
        {"request": request, "user": user, "active": "collections", "collection": None},
    )


@router.get("/collections/{collection_id}/edit", response_class=HTMLResponse)
async def edit_collection_form(
    request: Request,
    collection_id: str,
    user: UserContext = Depends(require_admin_ui),
):
    """Edit collection form."""
    return templates.TemplateResponse(
        "collection_form.html",
        {"request": request, "user": user, "active": "collections", "collection_id": collection_id},
    )


@router.get("/collections/{collection_name}/api", response_class=HTMLResponse)
async def collection_api_reference(
    request: Request,
    collection_name: str,
    user: UserContext = Depends(require_admin_ui),
):
    """View collection API reference with code examples."""
    return templates.TemplateResponse(
        "collection_detail.html",
        {"request": request, "user": user, "active": "collections", "collection_name": collection_name},
    )


@router.get("/collections/{collection_name}/records", response_class=HTMLResponse)
async def collection_records(
    request: Request,
    collection_name: str,
    user: UserContext = Depends(require_admin_ui),
):
    """View records in a collection."""
    return templates.TemplateResponse(
        "records.html",
        {"request": request, "user": user, "active": "collections", "collection_name": collection_name},
    )


@router.get("/collections/{collection_name}/records/new", response_class=HTMLResponse)
async def create_record_form(
    request: Request,
    collection_name: str,
    user: UserContext = Depends(require_admin_ui),
):
    """Create new record form."""
    return templates.TemplateResponse(
        "record_form.html",
        {"request": request, "user": user, "active": "collections", "collection_name": collection_name, "record": None},
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
        "record_detail.html",
        {"request": request, "user": user, "active": "collections", "collection_name": collection_name, "record_id": record_id},
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
        "record_form.html",
        {"request": request, "user": user, "active": "collections", "collection_name": collection_name, "record_id": record_id},
    )


@router.get("/files", response_class=HTMLResponse)
async def file_manager(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """File management page."""
    return templates.TemplateResponse(
        "files.html",
        {"request": request, "user": user, "active": "files"},
    )


@router.get("/webhooks", response_class=HTMLResponse)
async def admin_webhooks(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Webhook management page."""
    return templates.TemplateResponse(
        "webhooks.html",
        {"request": request, "user": user, "active": "webhooks"},
    )


@router.get("/plugins", response_class=HTMLResponse)
async def admin_plugins(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Plugins management page — lists all loaded plugin packages."""
    from app.core.plugin_registry import get_registry
    return templates.TemplateResponse(
        "plugins.html",
        {"request": request, "user": user, "active": "plugins",
         "plugins": get_registry().get_plugins()},
    )


@router.get("/hooks", response_class=HTMLResponse)
async def admin_hooks(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Hooks management page — lists all loaded Python hook files."""
    from app.core.hook_loader import get_loaded_hooks
    return templates.TemplateResponse(
        "hooks.html",
        {"request": request, "user": user, "active": "hooks", "hooks": get_loaded_hooks()},
    )


@router.get("/backups", response_class=HTMLResponse)
async def admin_backups(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Backup management page."""
    return templates.TemplateResponse(
        "backups.html",
        {"request": request, "user": user, "active": "backups"},
    )


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """System settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "user": user, "active": "settings"},
    )


@router.get("/settings/email", response_class=HTMLResponse)
async def admin_email_settings(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Email settings and SMTP configuration page."""
    from app.core.config import settings as app_settings
    return templates.TemplateResponse(
        "email_settings.html",
        {
            "request": request,
            "user": user,
            "active": "email_settings",
            "smtp_enabled": app_settings.SMTP_ENABLED,
            "smtp_host": app_settings.SMTP_HOST,
            "smtp_port": app_settings.SMTP_PORT,
            "smtp_user": app_settings.SMTP_USER,
            "smtp_from_email": app_settings.SMTP_FROM_EMAIL,
            "smtp_from_name": app_settings.SMTP_FROM_NAME,
            "security_notifications_enabled": app_settings.SECURITY_NOTIFICATIONS_ENABLED,
            "security_login_notifications": app_settings.SECURITY_LOGIN_NOTIFICATIONS,
        },
    )


@router.get("/profile", response_class=HTMLResponse)
async def admin_profile(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """User profile page."""
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "user": user, "active": "profile"},
    )


@router.get("/realtime", response_class=HTMLResponse)
async def admin_realtime(
    request: Request,
    user: UserContext = Depends(require_admin_ui),
):
    """Real-time features demo page."""
    return templates.TemplateResponse(
        "realtime.html",
        {"request": request, "user": user, "active": "realtime"},
    )


@router.get("/login", response_class=HTMLResponse)
async def admin_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin login page."""
    # Check if setup is needed
    result = await db.execute(select(User).limit(1))
    if not result.scalar_one_or_none():
        return RedirectResponse(url="/setup", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/setup", response_class=HTMLResponse)
async def admin_setup(request: Request, db: AsyncSession = Depends(get_db)):
    """Initial setup page for creating first admin user."""
    # Check if setup is already done
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        return RedirectResponse(url="/admin/login", status_code=302)

    return templates.TemplateResponse("setup.html", {"request": request})
